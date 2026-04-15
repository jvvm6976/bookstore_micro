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
from . import rag, recommender, behavior as beh
from ..clients import book_client, order_client, ship_client

logger = logging.getLogger(__name__)

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


# ── Intent handlers ───────────────────────────────────────────────────────────

def _handle_greeting(ctx: dict) -> dict:
    name = ctx.get('username', 'bạn')
    return {
        'text': (
            f"Xin chào {name}! 👋 Tôi là AI Assistant của CloudBooks.\n"
            "Tôi có thể giúp bạn:\n"
            "• 💡 Gợi ý sách phù hợp\n"
            "• 🔍 Tìm kiếm sách\n"
            "• 📦 Tra cứu đơn hàng\n"
            "• ❓ Giải đáp thắc mắc về chính sách\n\n"
            "Bạn cần hỗ trợ gì?"
        ),
        'intent': 'greeting',
    }


def _handle_recommend(ctx: dict, query: str) -> dict:
    customer_id = ctx.get('customer_id')
    if not customer_id:
        # Fallback: return popular books
        popular = beh.get_popular_books(limit=5)
        if popular:
            books = [book_client.get_book(p['book_id']) for p in popular]
            books = [b for b in books if b]
            lines = [_format_book(b) for b in books[:5]]
            return {
                'text': "📚 Sách phổ biến nhất hiện tại:\n\n" + "\n\n".join(lines),
                'intent': 'recommend',
                'books': books[:5],
            }
        return {
            'text': "Đăng nhập để nhận gợi ý cá nhân hóa dựa trên sở thích của bạn! 🎯",
            'intent': 'recommend',
        }

    recs = recommender.generate(customer_id, limit=5)
    if not recs:
        return {
            'text': "Chưa có đủ dữ liệu để gợi ý. Hãy xem thêm sách để tôi hiểu sở thích của bạn! 📖",
            'intent': 'recommend',
        }

    lines = []
    books = []
    for r in recs:
        book = r.get('book', {})
        if book:
            lines.append(_format_book(book) + f"\n   💡 Lý do: {r['reason']}")
            books.append(book)

    return {
        'text': "💡 Gợi ý sách dành riêng cho bạn:\n\n" + "\n\n".join(lines),
        'intent': 'recommend',
        'books': books,
        'recommendations': recs,
    }


def _handle_book_search(ctx: dict, query: str) -> dict:
    search_q = _extract_book_query(query)
    if not search_q or len(search_q) < 2:
        return {
            'text': "Bạn muốn tìm sách gì? Hãy cho tôi biết tên sách, tác giả hoặc thể loại nhé! 🔍",
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
            'text': f"Không tìm thấy sách nào với từ khóa '{search_q}'. Thử từ khóa khác nhé! 🔍",
            'intent': 'book_search',
        }

    lines = [_format_book(b) for b in books[:5]]
    return {
        'text': f"🔍 Kết quả tìm kiếm '{search_q}':\n\n" + "\n\n".join(lines),
        'intent': 'book_search',
        'books': books[:5],
    }


def _handle_order_status(ctx: dict, query: str) -> dict:
    customer_id = ctx.get('customer_id')
    if not customer_id:
        return {
            'text': "Vui lòng đăng nhập để tra cứu đơn hàng của bạn. 🔒",
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
            'text': "Bạn chưa có đơn hàng nào. Hãy mua sách ngay! 🛒",
            'intent': 'order_status',
        }

    lines = [_format_order(o) for o in orders[:5]]
    return {
        'text': "📦 Đơn hàng gần đây của bạn:\n\n" + "\n".join(lines),
        'intent': 'order_status',
        'orders': orders[:5],
    }


def _handle_faq(ctx: dict, query: str) -> dict:
    context = rag.build_context(query, top_k=2)
    entries = rag.retrieve(query, top_k=2)

    if not entries:
        return {
            'text': (
                "Tôi chưa có thông tin về câu hỏi này. "
                "Vui lòng liên hệ support@cloudbooks.vn để được hỗ trợ! 📧"
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
    # Try RAG as last resort
    entries = rag.retrieve(query, top_k=1)
    if entries:
        return {
            'text': (
                f"**{entries[0]['title']}**\n\n{entries[0]['content']}\n\n"
                "Bạn có muốn biết thêm điều gì không? 😊"
            ),
            'intent': 'faq',
        }
    return {
        'text': (
            "Xin lỗi, tôi chưa hiểu câu hỏi của bạn. 🤔\n"
            "Bạn có thể hỏi tôi về:\n"
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
