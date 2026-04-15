"""
Knowledge Base Module
──────────────────────
Manages KB entries (FAQ, policy, book info).
Supports:
  - Manual ingestion via API
  - Auto-ingestion from book catalog
  - Keyword extraction for retrieval
"""
import logging
import re
from ..models import KBEntry

logger = logging.getLogger(__name__)

# ── Default FAQ / Policy entries ─────────────────────────────────────────────

DEFAULT_KB = [
    {
        'category': 'faq',
        'title': 'Làm thế nào để đặt hàng?',
        'content': (
            'Để đặt hàng tại CloudBooks: '
            '1. Đăng nhập tài khoản. '
            '2. Tìm sách bạn muốn mua. '
            '3. Nhấn "Thêm vào giỏ hàng". '
            '4. Vào giỏ hàng, nhập địa chỉ giao hàng. '
            '5. Chọn phương thức thanh toán và nhấn "Đặt hàng".'
        ),
        'keywords': ['đặt hàng', 'mua sách', 'giỏ hàng', 'checkout', 'order', 'dat hang', 'mua sach'],
    },
    {
        'category': 'faq',
        'title': 'Chính sách đổi trả hàng',
        'content': (
            'CloudBooks chấp nhận đổi trả trong vòng 7 ngày kể từ ngày nhận hàng. '
            'Điều kiện: sách còn nguyên vẹn, chưa qua sử dụng, còn đầy đủ bao bì. '
            'Liên hệ support@cloudbooks.vn để được hỗ trợ.'
        ),
        'keywords': ['đổi trả', 'hoàn tiền', 'refund', 'return', 'chính sách', 'doi tra', 'hoan tien', 'chinh sach'],
    },
    {
        'category': 'policy',
        'title': 'Phương thức thanh toán',
        'content': (
            'CloudBooks hỗ trợ các phương thức thanh toán: '
            '1. Thẻ tín dụng/ghi nợ (Visa, Mastercard). '
            '2. COD - Thanh toán khi nhận hàng. '
            '3. Chuyển khoản ngân hàng. '
            'Tất cả giao dịch được mã hóa và bảo mật.'
        ),
        'keywords': ['thanh toán', 'payment', 'thẻ tín dụng', 'cod', 'chuyển khoản', 'thanh toan', 'the tin dung', 'chuyen khoan'],
    },
    {
        'category': 'policy',
        'title': 'Thời gian giao hàng',
        'content': (
            'Thời gian giao hàng tiêu chuẩn: 3-5 ngày làm việc. '
            'Giao hàng nhanh: 1-2 ngày làm việc (phụ phí thêm). '
            'Miễn phí vận chuyển cho đơn hàng từ 300.000đ trở lên.'
        ),
        'keywords': ['giao hàng', 'vận chuyển', 'shipping', 'delivery', 'thời gian', 'giao hang', 'van chuyen'],
    },
    {
        'category': 'faq',
        'title': 'Làm thế nào để theo dõi đơn hàng?',
        'content': (
            'Bạn có thể theo dõi đơn hàng bằng cách: '
            '1. Đăng nhập vào tài khoản. '
            '2. Vào mục "Đơn hàng của tôi". '
            '3. Chọn đơn hàng cần theo dõi để xem trạng thái và mã tracking.'
        ),
        'keywords': ['theo dõi', 'tracking', 'đơn hàng', 'trạng thái', 'order status'],
    },
    {
        'category': 'faq',
        'title': 'Làm thế nào để đăng ký tài khoản?',
        'content': (
            'Để đăng ký tài khoản CloudBooks: '
            '1. Nhấn nút "Đăng ký" ở góc trên bên phải. '
            '2. Điền tên đăng nhập, email và mật khẩu (tối thiểu 6 ký tự). '
            '3. Nhấn "Tạo tài khoản". '
            'Tài khoản sẽ được tạo ngay lập tức.'
        ),
        'keywords': ['đăng ký', 'tài khoản', 'register', 'signup', 'account'],
    },
    {
        'category': 'general',
        'title': 'Giới thiệu CloudBooks',
        'content': (
            'CloudBooks là nhà sách trực tuyến hàng đầu, cung cấp hàng nghìn đầu sách '
            'thuộc các thể loại: lập trình, khoa học, lịch sử, tiểu thuyết, toán học. '
            'Chúng tôi cam kết mang đến trải nghiệm mua sắm tốt nhất với giá cả hợp lý.'
        ),
        'keywords': ['cloudbooks', 'giới thiệu', 'about', 'nhà sách', 'bookstore'],
    },
]


def seed_default_kb():
    """Seed default FAQ/policy entries if KB is empty."""
    if KBEntry.objects.filter(source='default').exists():
        return 0
    count = 0
    for entry in DEFAULT_KB:
        KBEntry.objects.get_or_create(
            title=entry['title'],
            defaults={
                'category': entry['category'],
                'content':  entry['content'],
                'keywords': entry['keywords'],
                'source':   'default',
            }
        )
        count += 1
    logger.info("Seeded %d default KB entries", count)
    return count


def ingest_book(book: dict) -> KBEntry:
    """Create/update a KB entry from a book dict."""
    book_id = book.get('id')
    title   = book.get('title', f'Book {book_id}')
    author  = book.get('author', 'Unknown')
    cat     = book.get('category', '')
    desc    = book.get('description', '')
    price   = book.get('price', 0)

    content = (
        f"Sách '{title}' của tác giả {author}. "
        f"Thể loại: {cat}. Giá: {price}đ. "
    )
    if desc:
        content += f"Mô tả: {desc}"

    keywords = [
        title.lower(),
        author.lower() if author else '',
        cat,
        'sách', 'book',
    ]
    keywords = [k for k in keywords if k]

    entry, _ = KBEntry.objects.update_or_create(
        title=f"[BOOK] {title}",
        defaults={
            'category': 'book',
            'content':  content,
            'keywords': keywords,
            'source':   f'book:{book_id}',
        }
    )
    return entry


def _extract_keywords(text: str) -> list[str]:
    """Simple keyword extraction: lowercase words, remove stopwords."""
    stopwords = {'và', 'của', 'là', 'có', 'cho', 'với', 'trong', 'the', 'a', 'an', 'is', 'are', 'to'}
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if len(w) > 2 and w not in stopwords]


def add_entry(category: str, title: str, content: str,
              keywords: list = None, source: str = 'api') -> KBEntry:
    """Add a new KB entry."""
    if not keywords:
        keywords = _extract_keywords(title + ' ' + content)
    entry = KBEntry.objects.create(
        category=category,
        title=title,
        content=content,
        keywords=keywords,
        source=source,
    )
    logger.info("Added KB entry: [%s] %s", category, title)
    return entry


def get_stats() -> dict:
    from django.db.models import Count
    stats = KBEntry.objects.values('category').annotate(count=Count('id'))
    return {
        'total': KBEntry.objects.count(),
        'by_category': {s['category']: s['count'] for s in stats},
    }
