"""
Entity Extractor
─────────────────
Extracts structured entities from user messages.

Entities:
  book_title    – tên sách
  author        – tác giả
  category      – thể loại
  order_id      – mã đơn hàng
  price_range   – khoảng giá {min, max}
  quantity      – số lượng
  keyword       – từ khóa tìm kiếm chung
"""
import re
import logging

logger = logging.getLogger(__name__)

# ── Category mapping ──────────────────────────────────────────────────────────

CATEGORY_ALIASES = {
    'lap trinh':    'programming',
    'programming':  'programming',
    'code':         'programming',
    'python':       'programming',
    'java':         'programming',
    'javascript':   'programming',
    'khoa hoc':     'science',
    'science':      'science',
    'vat ly':       'science',
    'hoa hoc':      'science',
    'lich su':      'history',
    'history':      'history',
    'tieu thuyet':  'fiction',
    'fiction':      'fiction',
    'van hoc':      'fiction',
    'truyen':       'fiction',
    'toan':         'math',
    'math':         'math',
    'dai so':       'math',
    'giai tich':    'math',
}

# ── Prefix patterns to strip ──────────────────────────────────────────────────

SEARCH_PREFIXES = re.compile(
    r'^(tim|search|tim kiem|co sach|sach ve|sach cua|sach|cuon|quyen|'
    r'cho toi|ban co|shop co|goi y|recommend|de xuat|nen mua|'
    r'thong tin|chi tiet|gia cua|gia sach)\s+',
    re.IGNORECASE,
)

AUTHOR_PATTERNS = [
    re.compile(r'\b(tac gia|author|viet boi|cua tac gia)\s+([A-Za-z\s\u00C0-\u024F]+)', re.IGNORECASE),
    re.compile(r'\b(cua|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'),
]

PRICE_PATTERNS = [
    re.compile(r'(\d+)\s*(?:k|nghìn|nghin|000)?\s*(?:den|to|-)\s*(\d+)\s*(?:k|nghìn|nghin|000)?'),
    re.compile(r'(?:duoi|under|<)\s*(\d+)\s*(?:k|nghìn|nghin)?'),
    re.compile(r'(?:tren|over|>)\s*(\d+)\s*(?:k|nghìn|nghin)?'),
]

ORDER_ID_PATTERN = re.compile(r'(?:don|order|ma don|#)\s*#?\s*(\d{1,8})', re.IGNORECASE)


def extract(text: str) -> dict:
    """
    Extract all entities from text.
    Returns dict with found entities (only non-None values).
    """
    text_lower = text.lower()
    entities = {}

    # Order ID
    m = ORDER_ID_PATTERN.search(text_lower)
    if not m:
        # bare number that looks like an order ID
        m2 = re.search(r'\b(\d{1,6})\b', text_lower)
        if m2 and len(m2.group(1)) >= 1:
            entities['order_id'] = int(m2.group(1))
    else:
        entities['order_id'] = int(m.group(1))

    # Category
    for alias, canonical in CATEGORY_ALIASES.items():
        if alias in text_lower:
            entities['category'] = canonical
            break

    # Author
    for pat in AUTHOR_PATTERNS:
        m = pat.search(text)
        if m:
            entities['author'] = m.group(2).strip()
            break

    # Price range
    price_match = PRICE_PATTERNS[0].search(text_lower)
    if price_match:
        lo = _parse_price(price_match.group(1))
        hi = _parse_price(price_match.group(2))
        entities['price_range'] = {'min': lo, 'max': hi}
    else:
        under = PRICE_PATTERNS[1].search(text_lower)
        if under:
            entities['price_range'] = {'min': 0, 'max': _parse_price(under.group(1))}
        over = PRICE_PATTERNS[2].search(text_lower)
        if over:
            entities['price_range'] = {'min': _parse_price(over.group(1)), 'max': None}

    # Search keyword (clean up prefixes)
    keyword = SEARCH_PREFIXES.sub('', text_lower).strip()
    # Remove category if already extracted
    if 'category' in entities:
        for alias in CATEGORY_ALIASES:
            keyword = keyword.replace(alias, '').strip()
    if keyword and len(keyword) >= 2:
        entities['keyword'] = keyword

    logger.debug("Entities from '%s': %s", text[:50], entities)
    return entities


def _parse_price(s: str) -> float:
    """Parse price string like '50', '50k', '50000' → float."""
    s = s.strip().lower().replace(',', '')
    if s.endswith('k'):
        return float(s[:-1]) * 1000
    val = float(s)
    # If small number, assume it's in thousands
    if val < 1000:
        val *= 1000
    return val
