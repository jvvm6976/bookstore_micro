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
    {
        'category': 'faq',
        'title': 'Tôi có thể mua sách như thế nào nếu chưa đăng nhập?',
        'content': 'Bạn có thể xem sản phẩm và thêm vào giỏ hàng, nhưng để đặt hàng và theo dõi đơn thì cần đăng nhập tài khoản.',
        'keywords': ['chưa đăng nhập', 'guest', 'mua sách', 'dat hang', 'dang nhap'],
    },
    {
        'category': 'faq',
        'title': 'Tôi muốn tìm sách theo thể loại thì làm sao?',
        'content': 'Hãy nhập tên thể loại như lập trình, khoa học, lịch sử, tiểu thuyết hoặc toán học; hệ thống sẽ trả về các cuốn sách phù hợp nhất.',
        'keywords': ['the loai', 'tìm sách theo thể loại', 'tim sach', 'category', 'genre'],
    },
    {
        'category': 'faq',
        'title': 'Sách nào phù hợp cho người mới học lập trình?',
        'content': 'Người mới học lập trình thường bắt đầu với Clean Code, Python Crash Course hoặc The Pragmatic Programmer để nắm tư duy nền tảng và thực hành tốt hơn.',
        'keywords': ['người mới', 'lap trinh', 'python', 'clean code', 'pragmatic programmer'],
    },
    {
        'category': 'faq',
        'title': 'Tôi muốn mua sách dưới 300k có được gợi ý không?',
        'content': 'Có. Bạn chỉ cần nói rõ ngân sách, ví dụ dưới 300k hoặc 200000đ, hệ thống sẽ lọc các sách phù hợp với mức giá đó.',
        'keywords': ['dưới 300k', 'duoi 300k', 'ngân sách', 'budget', 'gia'],
    },
    {
        'category': 'faq',
        'title': 'Làm sao biết sách còn hàng hay không?',
        'content': 'Trạng thái tồn kho hiển thị ngay trên trang sản phẩm. Nếu bạn hỏi chatbot, hệ thống cũng có thể trả lời theo dữ liệu tồn kho hiện tại.',
        'keywords': ['còn hàng', 'con hang', 'tồn kho', 'stock', 'het hang'],
    },
    {
        'category': 'faq',
        'title': 'Tôi có thể đổi địa chỉ giao hàng sau khi đặt không?',
        'content': 'Nếu đơn chưa chuyển sang trạng thái giao hàng, bạn có thể liên hệ hỗ trợ để cập nhật địa chỉ. Khi đơn đã xuất kho thì việc đổi địa chỉ sẽ khó hơn.',
        'keywords': ['đổi địa chỉ', 'doi dia chi', 'giao hang', 'shipping address', 'sua dia chi'],
    },
    {
        'category': 'faq',
        'title': 'Có thể hủy đơn hàng sau khi đặt không?',
        'content': 'Đơn hàng có thể hủy nếu chưa thanh toán hoặc chưa được xử lý giao hàng. Hãy cung cấp mã đơn để được kiểm tra trạng thái.',
        'keywords': ['hủy đơn', 'huy don', 'cancel', 'order', 'ma don'],
    },
    {
        'category': 'policy',
        'title': 'Khi nào tôi nhận được hóa đơn?',
        'content': 'Hóa đơn điện tử sẽ được gửi sau khi đơn hàng được xác nhận thanh toán thành công. Nếu chưa nhận được, hãy kiểm tra email hoặc mục hóa đơn trong tài khoản.',
        'keywords': ['hóa đơn', 'hoa don', 'invoice', 'bill', 'thanh toán thành công'],
    },
    {
        'category': 'policy',
        'title': 'Có chương trình khuyến mãi nào cho khách hàng thân thiết không?',
        'content': 'Khách hàng thân thiết được tích điểm theo giá trị đơn hàng và có thể đổi điểm lấy ưu đãi, giảm giá hoặc quà tặng theo từng chiến dịch.',
        'keywords': ['khuyến mãi', 'khuyen mai', 'thân thiết', 'than thiet', 'tich diem', 'danh cho khach hang'],
    },
    {
        'category': 'faq',
        'title': 'Tôi cần hỗ trợ về tài khoản bị khóa thì làm gì?',
        'content': 'Hãy liên hệ hỗ trợ khách hàng, cung cấp email hoặc username để kiểm tra trạng thái tài khoản và mở khóa nếu xác thực thành công.',
        'keywords': ['tài khoản bị khóa', 'bi khoa', 'account locked', 'support', 'mo khoa'],
    },
    {
        'category': 'faq',
        'title': 'Làm sao để xem lịch sử mua hàng của tôi?',
        'content': 'Đăng nhập vào tài khoản và mở mục đơn hàng hoặc lịch sử mua hàng. Tại đó bạn sẽ thấy các đơn gần đây, trạng thái và chi tiết từng sản phẩm.',
        'keywords': ['lịch sử mua hàng', 'lich su mua hang', 'order history', 'don hang'],
    },
    {
        'category': 'faq',
        'title': 'Tôi muốn tìm sách giống với cuốn tôi đã thích thì sao?',
        'content': 'Bạn có thể nhập tên cuốn sách đã thích, hoặc hỏi kiểu “gợi ý sách tương tự”. Hệ thống sẽ ưu tiên các sách cùng thể loại, tác giả hoặc chủ đề.',
        'keywords': ['sách giống', 'sach tuong tu', 'similar', 'goi y', 'same genre'],
    },
    {
        'category': 'faq',
        'title': 'Phí ship được tính như thế nào?',
        'content': 'Phí ship phụ thuộc khu vực giao hàng và giá trị đơn. Đơn đủ điều kiện có thể được miễn phí vận chuyển; các đơn khác sẽ hiển thị phí ngay trước khi thanh toán.',
        'keywords': ['phí ship', 'phi ship', 'vận chuyển', 'mien phi ship', 'shipping fee'],
    },
    {
        'category': 'faq',
        'title': 'Tôi nên chọn phương thức thanh toán nào?',
        'content': 'Bạn có thể chọn thẻ, chuyển khoản, COD hoặc ví điện tử tùy nhu cầu. Nếu muốn nhanh, ví điện tử và thẻ thường xử lý tức thì hơn COD.',
        'keywords': ['phương thức thanh toán', 'thanh toan nao', 'cod', 'momo', 'vnpay', 'the'],
    },
    {
        'category': 'faq',
        'title': 'Tôi muốn hỏi về sản phẩm điện tử thì có được không?',
        'content': 'Có. Hệ thống ecommerce hiện hỗ trợ nhiều loại sản phẩm như sách, laptop, mobile, tablet, tai nghe, màn hình, chuột, loa, máy in, router và phụ kiện khác.',
        'keywords': ['điện tử', 'dien tu', 'laptop', 'mobile', 'tablet', 'phu kien'],
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
