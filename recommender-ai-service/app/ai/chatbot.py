"""
Chatbot Orchestrator
─────────────────────
Rule-based NLU + RAG context + template responses.
No external LLM dependency — runs fully offline.

Intent detection → context retrieval → response generation.

Intents:
  recommend       – gợi ý sách
  book_search     – tìm sách theo tên/tác giả/thể loại
  book_detail     – chi tiết một cuốn sách
  order_status    – tra cứu đơn hàng
  faq             – câu hỏi thường gặp / chính sách
  greeting        – chào hỏi
  fallback        – không nhận ra
"""
import logging
import re
from typing import Any

from . import rag, recommender, behavior as beh
from ..services.behavior_analysis import behavior_service
from ..clients import book_client, order_client, ship_client

logger = logging.getLogger(__name__)


def _variant(options: list[str], key: str = "") -> str:
    if not options:
        return ""
    idx = abs(hash(key or "default")) % len(options)
    return options[idx]

# ── Intent patterns ───────────────────────────────────────────────────────────

INTENT_PATTERNS = [
    ('greeting',     [r'\b(xin chao|hello|hi|chao|hey|xinchao)\b']),
    ('recommend',    [r'\b(goi y|recommend|de xuat|nen mua|mua gi|sach hay|sach nao|suggest)\b']),
    ('book_search',  [r'\b(tim|search|tim kiem|co sach|sach ve|sach cua|find|look)\b']),
    ('book_detail',  [r'\b(chi tiet|thong tin|gia|mo ta|tac gia|detail|info|price)\b']),
    ('order_status', [r'\b(don hang|order|theo doi|tracking|giao hang|van chuyen|trang thai|status)\b']),
    ('faq',          [r'\b(doi tra|hoan tien|thanh toan|chinh sach|policy|faq|hoi|giai dap|dang ky|tai khoan|payment|return|refund|account)\b']),
]


def detect_intent(text: str) -> str:
    text_lower = text.lower()
    for intent, patterns in INTENT_PATTERNS:
        for pat in patterns:
            if re.search(pat, text_lower):
                return intent
    return 'fallback'


def _extract_book_query(text: str) -> str:
    """Extract search term from user message."""
    # Remove common prefixes
    text = re.sub(r'^(tìm|search|tìm kiếm|có sách|sách về|sách của)\s*', '', text.lower()).strip()
    return text or text


def _format_book(book: dict) -> str:
    title  = book.get('title', 'N/A')
    author = book.get('author', 'N/A')
    price  = book.get('price', 0)
    stock  = book.get('stock', 0)
    cat    = book.get('category', '')
    return (
        f"📚 **{title}**\n"
        f"   ✍️ Tác giả: {author} | 📂 {cat}\n"
        f"   💰 Giá: {float(price):,.0f}đ | 📦 Kho: {stock} cuốn"
    )


def _format_order(order: dict) -> str:
    oid    = order.get('id', '?')
    status = order.get('status', '?')
    total  = order.get('total_amount', 0)
    date   = order.get('created_at', '')[:10] if order.get('created_at') else ''
    status_vi = {
        'pending':   '⏳ Chờ xử lý',
        'paid':      '✅ Đã thanh toán',
        'shipped':   '🚚 Đang giao',
        'delivered': '📬 Đã giao',
        'canceled':  '❌ Đã hủy',
    }.get(status, status)
    return f"📦 Đơn #{oid} | {status_vi} | {float(total):,.0f}đ | {date}"


def _load_interaction_totals(customer_id: int) -> dict[str, int]:
    try:
        from django.apps import apps

        CustomerBookInteraction = apps.get_model("app", "CustomerBookInteraction")
        totals: dict[str, int] = {}
        for ix in CustomerBookInteraction.objects.filter(customer_id=customer_id):
            totals[ix.interaction_type] = totals.get(ix.interaction_type, 0) + int(ix.count or 0)
        return totals
    except Exception as exc:
        logger.debug("Could not load interaction totals for C%s: %s", customer_id, exc)
        return {}


def _load_behavior_profile(customer_id: int | None) -> dict[str, Any] | None:
    if not customer_id:
        return None
    try:
        totals = _load_interaction_totals(customer_id)
        return behavior_service.analyze(customer_id, totals)
    except Exception as exc:
        logger.debug("Could not load behavior profile for C%s: %s", customer_id, exc)
        return None


def _behavior_tone(profile: dict[str, Any] | None, history: list[dict] | None) -> str:
    profile = profile or {}
    history = history or []
    segment = str(profile.get('customer_segment', '') or '').lower()
    categories = [str(item.get('category', '')).strip() for item in profile.get('preferred_categories', []) if isinstance(item, dict) and item.get('category')]
    categories = [cat for cat in categories if cat]

    if categories:
        return f"Mình thấy bạn hay để ý {', '.join(categories[:2])}, nên mình sẽ ưu tiên gợi ý đúng gu của bạn."
    if segment in {'champion', 'loyal'}:
        return "Mình sẽ đi thẳng vào vài lựa chọn hợp gu của bạn nhé."
    if segment in {'engaged', 'casual'}:
        return "Mình sẽ bám theo những gì bạn vừa xem để lọc sát hơn."
    if history and len(history) >= 4:
        return "Mình sẽ nối tiếp ngữ cảnh bạn vừa hỏi để đỡ phải lặp lại nhé."
    return "Mình sẽ cố trả lời sát với đúng nhu cầu bạn đang nói tới hơn."


def _friendly_follow_up(profile: dict[str, Any] | None, default: str) -> str:
    profile = profile or {}
    segment = str(profile.get('customer_segment', '') or '').lower()
    if segment in {'champion', 'loyal'}:
        return "Nếu bạn muốn, mình có thể rút gọn thêm theo tầm giá hoặc chốt ngay nhóm phù hợp nhất."
    if segment in {'engaged', 'casual'}:
        return "Nếu muốn, mình có thể lọc tiếp theo tầm giá, danh mục hoặc món cùng gu với bạn."
    return default


# ── Intent handlers ───────────────────────────────────────────────────────────

def _handle_greeting(ctx: dict) -> dict:
    name = ctx.get('username', 'bạn')
    profile = ctx.get('behavior_profile')
    history = ctx.get('history', []) or []
    key = f"greeting:{ctx.get('customer_id') or 0}"
    opener = _variant([
        "Mình ở đây để giúp bạn tìm đúng thứ đang cần nè.",
        "Mình sẵn sàng hỗ trợ bạn từ gợi ý đến tra cứu đơn hàng luôn.",
        "Có gì cứ hỏi thẳng mình nhé, mình lọc giúp cho nhanh.",
    ], key)
    return {
        'text': (
            f"Xin chào {name}! 👋 Mình là Ecommerce đây.\n"
            f"{opener}\n"
            f"{_behavior_tone(profile, history)}\n"
            "Bạn có thể nhắn cho mình kiểu này:\n"
            "• 💡 Gợi ý sản phẩm phù hợp\n"
            "• 🔍 Tìm kiếm sản phẩm\n"
            "• 📦 Tra cứu đơn hàng\n"
            "• ❓ Giải đáp thắc mắc về chính sách\n\n"
            "Bạn muốn mình giúp gì trước?"
        ),
        'intent': 'greeting',
    }


def _handle_recommend(ctx: dict, query: str) -> dict:
    customer_id = ctx.get('customer_id')
    profile = ctx.get('behavior_profile')
    history = ctx.get('history', []) or []
    if not customer_id:
        # Fallback: return popular books
        popular = beh.get_popular_books(limit=5)
        if popular:
            books = [book_client.get_book(p['book_id']) for p in popular]
            books = [b for b in books if b]
            lines = [_format_book(b) for b in books[:5]]
            return {
                'text': "📚 Mấy món đang được nhiều người xem nhất lúc này:\n\n" + "\n\n".join(lines),
                'intent': 'recommend',
                'books': books[:5],
            }
        return {
            'text': "Đăng nhập để mình gợi ý sát gu của bạn hơn nhé! 🎯",
            'intent': 'recommend',
        }

    recs = recommender.generate(customer_id, limit=5)
    if not recs:
        return {
            'text': "Mình chưa có đủ dữ liệu để gợi ý. Bạn xem thêm vài món nữa để mình hiểu gu của bạn hơn nhé! 📖",
            'intent': 'recommend',
        }

    lines = []
    books = []
    for r in recs:
        book = r.get('book', {})
        if book:
            lines.append(_format_book(book) + f"\n   💡 Lý do: {r['reason']}")
            books.append(book)

    lead = _variant([
        "💡 Mình gợi ý vài món hợp với bạn nè:",
        "💡 Đây là vài lựa chọn mình lọc ra cho bạn:",
        "💡 Mình chọn nhanh theo gu gần đây của bạn:",
    ], f"recommend:{customer_id}")
    if profile and profile.get('preferred_categories'):
        cats = [str(item.get('category', '')).strip() for item in profile.get('preferred_categories', []) if isinstance(item, dict) and item.get('category')]
        cats = [cat for cat in cats if cat]
        if cats:
            lead = f"💡 Mình chọn theo gu gần đây của bạn: {', '.join(cats[:2])}"
    elif profile and str(profile.get('customer_segment', '')).lower() in {'loyal', 'champion'}:
        lead = "💡 Mình lọc nhanh theo lịch sử mua sắm gần đây của bạn:"

    if history and len(history) >= 4 and lead == "💡 Gợi ý sách dành riêng cho bạn:":
        lead = "💡 Mình nối tiếp ngữ cảnh bạn vừa xem để gợi ý sát hơn:"

    return {
        'text': lead + "\n\n" + "\n\n".join(lines),
        'intent': 'recommend',
        'books': books,
        'recommendations': recs,
    }


def _handle_book_search(ctx: dict, query: str) -> dict:
    search_q = _extract_book_query(query)
    profile = ctx.get('behavior_profile')
    if not search_q or len(search_q) < 2:
        return {
            'text': _friendly_follow_up(profile, "Bạn muốn tìm món gì? Cho mình biết tên, tác giả hoặc thể loại nhé! 🔍"),
            'intent': 'book_search',
        }

    # Track search interaction if logged in
    customer_id = ctx.get('customer_id')
    if customer_id:
        # We don't have a specific book_id for search, skip tracking
        pass

    books = book_client.search_books(search_q)
    if not books:
        return {
            'text': f"Mình chưa tìm thấy món nào với từ khóa '{search_q}'. {_friendly_follow_up(profile, 'Bạn thử từ khóa khác nhé! 🔍')}",
            'intent': 'book_search',
        }

    lines = [_format_book(b) for b in books[:5]]
    intro = _variant([
        f"🔍 Mình tìm được mấy kết quả cho '{search_q}':",
        f"🔍 Dưới đây là các món khớp với '{search_q}':",
        f"🔍 Đây là vài lựa chọn liên quan đến '{search_q}':",
    ], f"search:{ctx.get('customer_id') or 0}:{search_q}")
    if profile and profile.get('preferred_categories'):
        cats = [str(item.get('category', '')).strip() for item in profile.get('preferred_categories', []) if isinstance(item, dict) and item.get('category')]
        cats = [cat for cat in cats if cat]
        if cats:
            intro = f"🔍 Kết quả tìm kiếm '{search_q}' theo gu bạn hay xem ({', '.join(cats[:2])}):"
    return {
        'text': intro + "\n\n" + "\n\n".join(lines),
        'intent': 'book_search',
        'books': books[:5],
    }


def _handle_order_status(ctx: dict, query: str) -> dict:
    customer_id = ctx.get('customer_id')
    if not customer_id:
        return {
            'text': "Bạn đăng nhập giúp mình nhé, rồi mình tra cứu đơn hàng cho bạn ngay. 🔒",
            'intent': 'order_status',
        }

    # Check if specific order ID mentioned
    order_id_match = re.search(r'#?(\d+)', query)
    if order_id_match:
        oid = int(order_id_match.group(1))
        order = order_client.get_order_detail(oid)
        if order:
            ship = ship_client.get_shipment_by_order(oid) or {}
            tracking = ship.get('tracking_number', 'Chưa có')
            ship_status = ship.get('status', '')
            ship_vi = {
                'processing': '🔄 Đang xử lý',
                'shipped':    '🚚 Đang giao',
                'delivered':  '📬 Đã giao',
                'cancelled':  '❌ Đã hủy',
            }.get(ship_status, ship_status)
            return {
                'text': (
                    f"{_format_order(order)}\n"
                    f"   🚚 Vận chuyển: {ship_vi}\n"
                    f"   📍 Tracking: {tracking}"
                ),
                'intent': 'order_status',
                'order': order,
            }

    # List recent orders
    orders = order_client.get_orders_by_customer(customer_id)
    if not orders:
        return {
            'text': "Mình chưa thấy đơn hàng nào của bạn cả. Khi nào mua xong, mình sẽ tra cứu ngay được nhé. 🛒",
            'intent': 'order_status',
        }

    lines = [_format_order(o) for o in orders[:5]]
    return {
        'text': "📦 Mấy đơn gần đây của bạn đây:\n\n" + "\n".join(lines),
        'intent': 'order_status',
        'orders': orders[:5],
    }


def _handle_faq(ctx: dict, query: str) -> dict:
    context = rag.build_context(query, top_k=2)
    entries = rag.retrieve(query, top_k=2)

    if not entries:
        return {
            'text': (
                "Mình chưa có thông tin cho câu hỏi này. "
                "Nếu cần, bạn có thể liên hệ support@ecommerce.vn để được hỗ trợ nhé. 📧"
            ),
            'intent': 'faq',
        }

    # Use the top entry as the answer
    top = entries[0]
    text = f"**{top['title']}**\n\n{top['content']}"
    if len(entries) > 1:
        text += f"\n\n---\n💡 Có thể bạn cũng quan tâm: **{entries[1]['title']}**"

    return {
        'text': text,
        'intent': 'faq',
        'kb_entries': entries,
    }


def _handle_fallback(ctx: dict, query: str) -> dict:
    profile = ctx.get('behavior_profile')
    # Try RAG as last resort
    entries = rag.retrieve(query, top_k=1)
    if entries:
        note = _friendly_follow_up(profile, "Bạn có muốn mình nói thêm chi tiết nào không? 😊")
        return {
            'text': (
                f"**{entries[0]['title']}**\n\n{entries[0]['content']}\n\n"
                f"{note}"
            ),
            'intent': 'faq',
        }
    return {
        'text': (
            "Mình chưa hiểu ý bạn lắm. 🤔\n"
            "Bạn có thể hỏi mình theo mấy hướng này:\n"
            "• Gợi ý sách\n"
            "• Tìm kiếm sách\n"
            "• Trạng thái đơn hàng\n"
            "• Chính sách đổi trả, thanh toán"
        ),
        'intent': 'fallback',
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def chat(message: str, context: dict = None) -> dict:
    """
    Process a user message and return a response dict.

    context: {
        customer_id: int | None,
        username: str | None,
        history: list[{role, content}]  # last N messages
    }
    """
    ctx = context or {}
    if ctx.get('customer_id') and 'behavior_profile' not in ctx:
        ctx['behavior_profile'] = _load_behavior_profile(ctx.get('customer_id'))
    intent = detect_intent(message)
    logger.info("Chat intent=%s msg=%s", intent, message[:60])

    if intent == 'greeting':
        response = _handle_greeting(ctx)
    elif intent == 'recommend':
        response = _handle_recommend(ctx, message)
    elif intent == 'book_search':
        response = _handle_book_search(ctx, message)
    elif intent == 'order_status':
        response = _handle_order_status(ctx, message)
    elif intent == 'faq':
        response = _handle_faq(ctx, message)
    else:
        response = _handle_fallback(ctx, message)

    response['message'] = message
    return response
