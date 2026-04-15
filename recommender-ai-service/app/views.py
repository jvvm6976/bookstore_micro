"""
AI Assistant Service – Views
─────────────────────────────
Endpoints:
  /api/recommendations/          – GET list / generate
  /api/recommendations/track/    – POST track interaction
  /api/recommendations/behavior/ – GET behavior profile
  /api/recommendations/popular/  – GET popular books

  /api/ai/chat/                  – POST chatbot message
  /api/ai/kb/                    – GET/POST knowledge base
  /api/ai/kb/ingest_books/       – POST ingest books from book-service
  /api/ai/kb/seed/               – POST seed default FAQ
  /api/ai/health/                – GET health check
"""
import uuid
import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    CustomerBookInteraction, CustomerBehaviorProfile,
    Recommendation, KBEntry, ChatSession, ChatMessage,
)
from .serializers import (
    CustomerBookInteractionSerializer, CustomerBehaviorProfileSerializer,
    RecommendationSerializer, KBEntrySerializer,
    ChatSessionSerializer, ChatMessageSerializer,
)
from .ai import behavior as beh, recommender, kb as kb_module, rag, chatbot
from .clients import book_client

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(data, code=200):
    return Response(data, status=code)

def _err(msg, code=400):
    return Response({'error': msg}, status=code)


# ═══════════════════════════════════════════════════════════
# RECOMMENDATION ENDPOINTS
# ═══════════════════════════════════════════════════════════

@api_view(['GET'])
def recommendations_list(request):
    """
    GET /api/recommendations/?customer_id=<id>&limit=<n>&refresh=1
    Returns personalized recommendations.
    """
    customer_id = request.query_params.get('customer_id')
    limit       = int(request.query_params.get('limit', 8))
    refresh     = request.query_params.get('refresh', '0') == '1'

    if not customer_id:
        # Return popular books for anonymous users
        popular = beh.get_popular_books(limit=limit)
        books = []
        for p in popular:
            book = book_client.get_book(p['book_id'])
            if book:
                books.append({**book, 'popularity_score': p['total_score']})
        return _ok({'source': 'popular', 'recommendations': books})

    customer_id = int(customer_id)

    # Use cache unless refresh requested
    if not refresh:
        cached = recommender.get_cached(customer_id)
        if cached:
            return _ok({
                'customer_id': customer_id,
                'source': 'cache',
                'recommendations': cached,
            })

    recs = recommender.generate(customer_id, limit=limit)
    return _ok({
        'customer_id': customer_id,
        'source': 'generated',
        'recommendations': recs,
    })


@api_view(['POST'])
def track_interaction(request):
    """
    POST /api/recommendations/track/
    Body: {customer_id, book_id, interaction_type, rating?}
    interaction_type: view | search | cart | purchase | rate
    """
    customer_id      = request.data.get('customer_id')
    book_id          = request.data.get('book_id')
    interaction_type = request.data.get('interaction_type', 'view')
    rating           = request.data.get('rating')

    if not customer_id or not book_id:
        return _err('customer_id and book_id are required')

    result = beh.track(
        customer_id=int(customer_id),
        book_id=int(book_id),
        interaction_type=interaction_type,
        rating=int(rating) if rating else None,
    )
    return _ok(result, 200)


@api_view(['GET'])
def behavior_profile(request):
    """
    GET /api/recommendations/behavior/?customer_id=<id>&refresh=1
    Returns behavior profile with likely-to-buy books.
    """
    customer_id = request.query_params.get('customer_id')
    if not customer_id:
        return _err('customer_id required')

    customer_id = int(customer_id)
    refresh = request.query_params.get('refresh', '0') == '1'

    if refresh:
        profile = beh.build_profile(customer_id)
    else:
        profile = beh.get_profile(customer_id)
        if not profile:
            profile = beh.build_profile(customer_id)

    # Enrich likely_to_buy with book details
    likely_books = []
    for bid in profile.likely_to_buy[:10]:
        book = book_client.get_book(bid)
        score = beh.get_book_scores(customer_id).get(bid, 0)
        if book:
            likely_books.append({**book, 'behavior_score': score})

    return _ok({
        'customer_id':    customer_id,
        'top_categories': profile.top_categories,
        'top_authors':    profile.top_authors,
        'total_score':    profile.total_score,
        'likely_to_buy':  likely_books,
        'updated_at':     profile.updated_at.isoformat(),
    })


@api_view(['GET'])
def popular_books(request):
    """
    GET /api/recommendations/popular/?limit=10
    Returns globally popular books based on interaction scores.
    """
    limit = int(request.query_params.get('limit', 10))
    popular = beh.get_popular_books(limit=limit)
    result = []
    for p in popular:
        book = book_client.get_book(p['book_id'])
        if book:
            result.append({
                **book,
                'popularity_score':    p['total_score'],
                'interaction_count':   p['interaction_count'],
            })
    return _ok({'popular_books': result, 'count': len(result)})


# ═══════════════════════════════════════════════════════════
# CHATBOT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@api_view(['POST'])
def chat(request):
    """
    POST /api/ai/chat/
    Body: {
        message: str,
        session_id?: str,       # omit to start new session
        customer_id?: int,
        username?: str
    }
    """
    message     = (request.data.get('message') or '').strip()
    session_id  = request.data.get('session_id') or str(uuid.uuid4())
    customer_id = request.data.get('customer_id')
    username    = request.data.get('username', 'bạn')

    if not message:
        return _err('message is required')

    # Get or create session
    session, _ = ChatSession.objects.get_or_create(
        session_id=session_id,
        defaults={'customer_id': customer_id},
    )
    if customer_id and not session.customer_id:
        session.customer_id = customer_id
        session.save(update_fields=['customer_id'])

    # Build history context (last 6 messages)
    history = list(
        session.messages.order_by('-timestamp')[:6]
        .values('role', 'content')
    )
    history.reverse()

    # Save user message
    ChatMessage.objects.create(
        session=session,
        role='user',
        content=message,
    )

    # Run chatbot
    ctx = {
        'customer_id': int(customer_id) if customer_id else None,
        'username':    username,
        'history':     history,
    }
    response = chatbot.chat(message, ctx)

    # Save assistant message
    ChatMessage.objects.create(
        session=session,
        role='assistant',
        content=response['text'],
        metadata={
            'intent': response.get('intent', 'unknown'),
            'books':  [b.get('id') for b in response.get('books', []) if b.get('id')],
        },
    )

    return _ok({
        'session_id': session_id,
        'response':   response['text'],
        'intent':     response.get('intent', 'unknown'),
        'books':      response.get('books', []),
        'orders':     response.get('orders', []),
        'kb_entries': response.get('kb_entries', []),
    })


@api_view(['GET'])
def chat_history(request):
    """
    GET /api/ai/chat/history/?session_id=<id>
    """
    session_id = request.query_params.get('session_id')
    if not session_id:
        return _err('session_id required')
    try:
        session = ChatSession.objects.get(session_id=session_id)
    except ChatSession.DoesNotExist:
        return _err('Session not found', 404)
    messages = session.messages.all().values('role', 'content', 'timestamp', 'metadata')
    return _ok({
        'session_id': session_id,
        'messages':   list(messages),
    })


# ═══════════════════════════════════════════════════════════
# KNOWLEDGE BASE ENDPOINTS
# ═══════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
def kb_list(request):
    """
    GET  /api/ai/kb/?category=<cat>  – list entries
    POST /api/ai/kb/                 – add entry
    """
    if request.method == 'GET':
        cat = request.query_params.get('category')
        qs  = KBEntry.objects.all().order_by('-updated_at')
        if cat:
            qs = qs.filter(category=cat)
        return _ok({
            'count':   qs.count(),
            'entries': KBEntrySerializer(qs[:50], many=True).data,
            'stats':   kb_module.get_stats(),
        })

    # POST
    category = request.data.get('category', 'general')
    title    = request.data.get('title', '').strip()
    content  = request.data.get('content', '').strip()
    keywords = request.data.get('keywords', [])

    if not title or not content:
        return _err('title and content are required')

    entry = kb_module.add_entry(category, title, content, keywords, source='api')
    return _ok(KBEntrySerializer(entry).data, 201)


@api_view(['POST'])
def kb_seed(request):
    """POST /api/ai/kb/seed/ – seed default FAQ/policy entries."""
    count = kb_module.seed_default_kb()
    return _ok({'seeded': count, 'message': f'Seeded {count} default KB entries'})


@api_view(['POST'])
def kb_ingest_books(request):
    """
    POST /api/ai/kb/ingest_books/
    Fetches all books from book-service and ingests them into KB.
    """
    books = book_client.get_all_books()
    if not books:
        return _err('Could not fetch books from book-service', 503)

    ingested = 0
    for book in books:
        kb_module.ingest_book(book)
        ingested += 1

    return _ok({'ingested': ingested, 'message': f'Ingested {ingested} books into KB'})


@api_view(['GET'])
def kb_search(request):
    """
    GET /api/ai/kb/search/?q=<query>&top_k=3
    """
    query = request.query_params.get('q', '')
    top_k = int(request.query_params.get('top_k', 3))
    if not query:
        return _err('q parameter required')
    results = rag.retrieve(query, top_k=top_k)
    return _ok({'query': query, 'results': results})


# ═══════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════

@api_view(['GET'])
def health(request):
    return _ok({
        'service': 'recommender-ai-service',
        'status':  'healthy',
        'modules': ['behavior', 'recommender', 'kb', 'rag', 'chatbot'],
        'kb_stats': kb_module.get_stats(),
    })
