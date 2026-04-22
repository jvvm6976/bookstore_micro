"""
EntityExtractor
───────────────
Extracts structured entities from user messages.

Entities:
  product_keywords  – list[str]
  category          – str | None
  budget_min        – float | None
  budget_max        – float | None
  order_id          – int | None
  policy_topic      – str | None
  rating_threshold  – float | None
  author            – str | None
  brand             – str | None
"""
from __future__ import annotations
import time
import re
import logging
from typing import Any

from ..clients.catalog_client import catalog_client

logger = logging.getLogger(__name__)
_LEXICON_TTL_SECONDS = 300
_LEXICON_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "value": {"category": {}, "brand": {}, "type": {}, "product": {}},
}

_STATIC_LEXICON: dict[str, dict[str, list[str]]] = {
    "category": {
        "programming": [
            "lập trình", "lap trinh", "programming", "coding", "code", "dev", "developer",
            "python", "java", "javascript", "golang", "php", "c++", "c#",
        ],
        "science": [
            "khoa học", "khoa hoc", "science", "physics", "chemistry", "biology", "astronomy", "astro",
        ],
        "history": [
            "lịch sử", "lich su", "history", "historical",
        ],
        "fiction": [
            "tiểu thuyết", "tieu thuyet", "fiction", "novel", "truyện", "truyen", "văn học", "van hoc",
        ],
        "math": [
            "toán", "toan", "math", "mathematics", "đại số", "dai so", "giải tích", "giai tich", "hình học", "hinh hoc",
        ],
        "business": [
            "business", "kinh doanh", "quan tri", "quản trị", "startup", "khởi nghiệp", "khoi nghiep",
        ],
        "marketing": [
            "marketing", "digital marketing", "seo", "content marketing", "branding",
        ],
        "self-help": [
            "self help", "self-help", "phát triển bản thân", "phat trien ban than", "kỹ năng sống", "ky nang song", "motivation",
        ],
        "technology": [
            "công nghệ", "cong nghe", "technology", "it", "tech",
        ],
        "office": [
            "văn phòng", "van phong", "office", "office supplies", "dụng cụ học tập", "dung cu hoc tap",
        ],
        "gaming": [
            "gaming", "game", "esports", "chơi game", "choi game",
        ],
    },
    "brand": {
        "apple": ["apple", "iphone", "ipad", "macbook", "airpods"],
        "samsung": ["samsung", "galaxy"],
        "xiaomi": ["xiaomi", "mi", "redmi", "poco"],
        "oppo": ["oppo"],
        "vivo": ["vivo"],
        "realme": ["realme"],
        "asus": ["asus", "rog"],
        "lenovo": ["lenovo", "thinkpad", "legion"],
        "dell": ["dell", "xps", "inspiron", "alienware"],
        "hp": ["hp", "omen", "pavilion"],
        "acer": ["acer", "nitro", "predator"],
        "msi": ["msi"],
        "logitech": ["logitech", "logi"],
        "razer": ["razer"],
        "sony": ["sony", "playstation", "ps5"],
        "jbl": ["jbl"],
        "bose": ["bose"],
        "anker": ["anker"],
        "canon": ["canon"],
        "nikon": ["nikon"],
        "fujifilm": ["fujifilm", "fuji"],
        "tp-link": ["tp-link", "tplink", "deco", "archer"],
        "d-link": ["d-link", "dlink"],
        "wd": ["wd", "western digital"],
        "seagate": ["seagate"],
    },
    "type": {
        "book": ["sách", "sach", "book", "ebook"],
        "laptop": ["laptop", "notebook", "ultrabook", "macbook"],
        "desktop": ["desktop", "pc", "máy tính bàn", "may tinh ban"],
        "phone": ["điện thoại", "dien thoai", "phone", "smartphone", "mobile"],
        "tablet": ["tablet", "ipad"],
        "earphone": ["tai nghe", "headphone", "earphone", "earbuds", "airpods"],
        "keyboard": ["bàn phím", "ban phim", "keyboard"],
        "mouse": ["chuột", "chuot", "mouse"],
        "monitor": ["màn hình", "man hinh", "monitor", "display"],
        "camera": ["camera", "máy ảnh", "may anh", "webcam"],
        "speaker": ["loa", "speaker"],
        "printer": ["máy in", "may in", "printer"],
        "router": ["router", "wifi", "modem", "mesh"],
        "storage": ["ổ cứng", "o cung", "ssd", "hdd", "storage", "usb"],
        "console": ["console", "máy chơi game", "may choi game", "playstation", "xbox", "nintendo"],
        "smartwatch": ["smartwatch", "đồng hồ thông minh", "dong ho thong minh", "watch"],
    },
    "product": {
        "clean code": ["clean code"],
        "the pragmatic programmer": ["the pragmatic programmer", "pragmatic programmer"],
        "design patterns": ["design patterns"],
        "python crash course": ["python crash course"],
        "introduction to algorithms": ["introduction to algorithms", "clrs"],
        "dune": ["dune"],
        "cosmos": ["cosmos"],
        "sapiens": ["sapiens"],
        "homo deus": ["homo deus"],
        "1984": ["1984"],
        "the great gatsby": ["the great gatsby", "great gatsby"],
    },
}

# Category keyword map (ASCII + Vietnamese)
def _normalize_terms(value: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", value.lower()).strip()
    if not cleaned:
        return []
    variants = {cleaned}
    variants.add(cleaned.replace("-", " "))
    variants.add(cleaned.replace(" ", ""))
    variants.add(cleaned.replace("-", ""))
    return [term for term in variants if term]


def _push_alias(map_data: dict[str, set[str]], key: str, *values: str) -> None:
    bucket = map_data.setdefault(key, set())
    for value in values:
        for term in _normalize_terms(str(value)):
            bucket.add(term)


def _extract_terms_from_name(name: str) -> list[str]:
    raw = re.sub(r"[^\w\s\-]+", " ", str(name).lower())
    tokens = [token for token in raw.split() if len(token) >= 3]
    if not tokens:
        return []
    joined = [" ".join(tokens[:2]), " ".join(tokens[:3])] if len(tokens) >= 2 else []
    return list(dict.fromkeys(tokens + joined))


def _build_catalog_lexicon() -> dict[str, dict[str, list[str]]]:
    category_map: dict[str, set[str]] = {}
    brand_map: dict[str, set[str]] = {}
    type_map: dict[str, set[str]] = {}
    product_map: dict[str, set[str]] = {}

    try:
        products = catalog_client.get_all_products(limit=1000)
    except Exception as exc:
        logger.debug("Could not load catalog lexicon: %s", exc)
        products = []

    for product in products:
        category_detail = product.get("category_detail") if isinstance(product.get("category_detail"), dict) else {}
        brand_detail = product.get("brand_detail") if isinstance(product.get("brand_detail"), dict) else {}
        type_detail = product.get("type_detail") if isinstance(product.get("type_detail"), dict) else {}

        category_slug = str(category_detail.get("slug") or product.get("category") or "").strip()
        category_name = str(category_detail.get("name") or "").strip()
        brand_slug = str(brand_detail.get("slug") or product.get("brand") or "").strip()
        brand_name = str(brand_detail.get("name") or "").strip()
        type_slug = str(type_detail.get("slug") or product.get("product_type") or product.get("type") or "").strip()
        type_name = str(type_detail.get("name") or "").strip()
        product_title = str(product.get("title") or product.get("name") or "").strip()

        if category_slug:
            _push_alias(category_map, category_slug, category_slug, category_name)
        if brand_slug:
            _push_alias(brand_map, brand_slug, brand_slug, brand_name)
        if type_slug:
            _push_alias(type_map, type_slug, type_slug, type_name)

        if product_title:
            canonical_title = re.sub(r"\s+", " ", product_title.lower()).strip()
            _push_alias(product_map, canonical_title, canonical_title)

        title = str(product.get("title") or product.get("name") or "")
        for term in _extract_terms_from_name(title):
            if brand_slug:
                _push_alias(brand_map, brand_slug, term)
            if type_slug:
                _push_alias(type_map, type_slug, term)
            if category_slug and category_slug not in {"reading"}:
                _push_alias(category_map, category_slug, term)
            if product_title:
                _push_alias(product_map, canonical_title, term)

    return {
        "category": {k: sorted(v) for k, v in category_map.items()},
        "brand": {k: sorted(v) for k, v in brand_map.items()},
        "type": {k: sorted(v) for k, v in type_map.items()},
        "product": {k: sorted(v) for k, v in product_map.items()},
    }


def _merge_lexicon_section(dynamic_section: dict[str, list[str]], static_section: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, set[str]] = {}
    for key, values in static_section.items():
        _push_alias(merged, key, *values)
    for key, values in dynamic_section.items():
        _push_alias(merged, key, *values)
    return {k: sorted(v) for k, v in merged.items()}


def _get_combined_lexicon() -> dict[str, dict[str, list[str]]]:
    dynamic = _get_catalog_lexicon()
    return {
        "category": _merge_lexicon_section(dynamic.get("category", {}), _STATIC_LEXICON.get("category", {})),
        "brand": _merge_lexicon_section(dynamic.get("brand", {}), _STATIC_LEXICON.get("brand", {})),
        "type": _merge_lexicon_section(dynamic.get("type", {}), _STATIC_LEXICON.get("type", {})),
        "product": _merge_lexicon_section(dynamic.get("product", {}), _STATIC_LEXICON.get("product", {})),
    }


def _contains_term(text: str, term: str) -> bool:
    if not term or len(term) < 2:
        return False
    if " " in term:
        return term in text
    return bool(re.search(rf"\b{re.escape(term)}\b", text, re.I))


def _best_match_key(text: str, lexicon: dict[str, list[str]]) -> str | None:
    best_key: str | None = None
    best_len = -1
    for key, keywords in lexicon.items():
        for kw in keywords:
            if _contains_term(text, kw):
                if len(kw) > best_len:
                    best_key = key
                    best_len = len(kw)
    return best_key


def _get_catalog_lexicon() -> dict[str, dict[str, list[str]]]:
    now = time.time()
    if now < float(_LEXICON_CACHE.get("expires_at") or 0):
        return _LEXICON_CACHE["value"]

    lexicon = _build_catalog_lexicon()
    if not (lexicon.get("category") or lexicon.get("brand") or lexicon.get("type")):
        logger.debug("Catalog lexicon is empty; preserving previous dynamic cache")
        _LEXICON_CACHE["expires_at"] = now + 60
        return _LEXICON_CACHE["value"]

    _LEXICON_CACHE["value"] = lexicon
    _LEXICON_CACHE["expires_at"] = now + _LEXICON_TTL_SECONDS
    return lexicon

# Policy topic map
_POLICY_MAP: dict[str, list[str]] = {
    "return":   ["đổi trả", "doi tra", "hoàn tiền", "hoan tien", "refund", "return", "trả hàng", "tra hang", "đổi hàng", "doi hang", "hàng lỗi", "hang loi", "điều kiện", "dieu kien"],
    "payment":  ["thanh toán", "thanh toan", "payment", "pay", "thẻ", "cod", "chuyển khoản", "chuyen khoan", "ví điện tử", "vi dien tu", "ewallet", "e-wallet", "momo", "vnpay", "zalopay"],
    "shipping": ["giao hàng", "giao hang", "vận chuyển", "van chuyen", "ship", "delivery", "nhận hàng", "nhan hang"],
    "account":  ["tài khoản", "tai khoan", "account", "đăng ký", "dang ky", "register"],
    "warranty": ["bảo hành", "bao hanh", "warranty", "guarantee"],
}

_CATEGORY_HINTS: dict[str, list[str]] = {
    "programming": ["lập trình", "lap trinh", "programming", "python", "code", "coding"],
    "science": ["khoa học", "khoa hoc", "science"],
    "history": ["lịch sử", "lich su", "history"],
    "self-help": ["self help", "self-help", "phát triển bản thân", "phat trien ban than"],
    "marketing": ["marketing"],
    "business": ["business", "kinh doanh", "quan tri"],
    "fiction": ["fiction", "tiểu thuyết", "tieu thuyet", "novel"],
    "math": ["math", "toán", "toan", "mathematics"],
}


def _extract_budget(text: str) -> tuple[float | None, float | None]:
    """Extract budget_min and budget_max from text."""
    budget_min: float | None = None
    budget_max: float | None = None

    # Pattern: "dưới 300k", "under 300000", "< 500k"
    under = re.search(r"(?:dưới|duoi|under|<|tầm|tam)\s*(\d+(?:[.,]\d+)?)\s*(?:k|nghìn|nghin|đồng|dong|vnd)?", text, re.I)
    if under:
        val = float(under.group(1).replace(",", "."))
        budget_max = val * 1000 if val < 10000 else val

    # Pattern: "từ 100k đến 300k", "100k-300k"
    range_match = re.search(
        r"(?:từ|tu|from)?\s*(\d+(?:[.,]\d+)?)\s*(?:k|nghìn)?\s*(?:đến|den|to|-)\s*(\d+(?:[.,]\d+)?)\s*(?:k|nghìn)?",
        text, re.I
    )
    if range_match:
        lo = float(range_match.group(1).replace(",", "."))
        hi = float(range_match.group(2).replace(",", "."))
        budget_min = lo * 1000 if lo < 10000 else lo
        budget_max = hi * 1000 if hi < 10000 else hi

    # Pattern: "trên 200k", "above 200k", "> 200000"
    above = re.search(r"(?:trên|tren|above|>)\s*(\d+(?:[.,]\d+)?)\s*(?:k|nghìn|nghin|đồng|dong|vnd)?", text, re.I)
    if above and not range_match:
        val = float(above.group(1).replace(",", "."))
        budget_min = val * 1000 if val < 10000 else val

    return budget_min, budget_max


def _extract_order_id(text: str) -> int | None:
    m = re.search(r"(?:đơn|don|order|#|mã đơn|ma don|đơn mã|don ma|mã|ma)\s*#?\s*(\d+)", text, re.I)
    if m:
        return int(m.group(1))
    # bare number if context is order
    m2 = re.search(r"\b(\d{3,8})\b", text)
    if m2:
        return int(m2.group(1))
    return None


def _extract_category(text: str) -> str | None:
    text_lower = text.lower()
    # Semantic category hints cover book-domain intents even when live catalog categories are sparse.
    for category, hints in _CATEGORY_HINTS.items():
        for hint in hints:
            if hint in text_lower:
                return category

    combined = _get_combined_lexicon()["category"]
    return _best_match_key(text_lower, combined)


def _extract_brand(text: str) -> str | None:
    text_lower = text.lower()
    lexicon = _get_combined_lexicon()["brand"]
    return _best_match_key(text_lower, lexicon)


def _extract_product_type(text: str) -> str | None:
    text_lower = text.lower()
    lexicon = _get_combined_lexicon()["type"]
    return _best_match_key(text_lower, lexicon)


def _extract_specific_product(text: str) -> str | None:
    text_lower = text.lower()
    lexicon = _get_combined_lexicon()["product"]
    return _best_match_key(text_lower, lexicon)


def _extract_policy_topic(text: str) -> str | None:
    text_lower = text.lower()
    for topic, keywords in _POLICY_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                return topic
    return None


def _extract_rating_threshold(text: str) -> float | None:
    m = re.search(r"(?:rating|đánh giá|danh gia|sao|star)\s*(?:từ|tu|>=|>|trên|tren)?\s*([1-5](?:\.\d)?)", text, re.I)
    if m:
        return float(m.group(1))
    return None


def _extract_author(text: str) -> str | None:
    m = re.search(r"(?:tác giả|tac gia|author|của|cua)\s+([A-ZÀ-Ỹa-zà-ỹ][A-ZÀ-Ỹa-zà-ỹ\s\.]{2,40})", text)
    if m:
        return m.group(1).strip()
    return None


def _is_price_question(text: str) -> bool:
    t = text.lower()
    if re.search(r"\b(bao nhiêu tiền|bao nhieu tien|giá bao nhiêu|gia bao nhieu|price|cost|mức giá|muc gia|tầm giá|tam gia)\b", t, re.I):
        return True
    if re.search(r"\b(khoảng|khoang)\s*\d+(?:[.,]\d+)?\s*(k|nghìn|nghin|triệu|trieu|đồng|dong|vnd)?\s*(đến|den|-|to)\s*\d+", t, re.I):
        return True
    if re.search(r"\b(từ|tu|from)\s*\d+(?:[.,]\d+)?\s*(k|nghìn|nghin|triệu|trieu|đồng|dong|vnd)?\s*(đến|den|-|to)\s*\d+", t, re.I):
        return True
    if re.search(r"\b(sách|sach)\s*(trên|tren|dưới|duoi)\s*\d+\b", t, re.I):
        return True
    if re.search(r"\b(sách|sach)\s*(từ|tu)\s*\d+\s*(?:k|nghìn|nghin|đồng|dong|vnd)?\s*(đến|den|-)\s*\d+\s*(?:k|nghìn|nghin|đồng|dong|vnd)?\b", t, re.I):
        return True
    if re.search(r"\b(trên|tren|dưới|duoi)\s*\d+\s*(k|nghìn|nghin|đồng|dong|vnd)?\b", t, re.I):
        return True
    if re.search(r"\bgia\b", t) and not re.search(r"\btac\s+gia\b", t):
        return True
    if re.search(r"\b(giá|gia)\s*(dưới|duoi|trên|tren|<|>|từ|tu|đến|den|k|vnd|đồng|dong|\d)", t, re.I):
        return True
    return False


def _is_stock_question(text: str) -> bool:
    return bool(re.search(r"\b(còn hàng không|con hang khong|còn hàng|con hang|còn không|con khong|hết hàng chưa|het hang chua|hết hàng không|het hang khong|in stock|available|availability)\b", text, re.I))


def _is_best_price_question(text: str) -> bool:
    return bool(re.search(r"\b(giá\s+tốt\s+nhất|gia\s+tot\s+nhat|rẻ\s+nhất|re\s+nhat|cheapest|best\s+price|giá\s+thấp\s+nhất|gia\s+thap\s+nhat)\b", text, re.I))


def _is_compare_price_question(text: str) -> bool:
    return bool(re.search(r"\b(rẻ hơn|re hon|đắt hơn|dat hon|cao hơn|thấp hơn|thap hon|so sánh giá|so sanh gia|so sánh|so sanh|compare|đắt nhất|dat nhat)\b", text, re.I))


def _is_next_book_question(text: str) -> bool:
    return bool(re.search(r"\b(đọc cuốn nào tiếp|doc cuon nao tiep|mua cuốn nào tiếp|mua cuon nao tiep|nên đọc cuốn nào tiếp|nen doc cuon nao tiep|next book|đọc tiếp|doc tiep)\b", text, re.I))


def _is_bestseller_question(text: str) -> bool:
    return bool(re.search(r"\b(bán chạy|ban chay|best\s*seller|popular|phổ biến|pho bien|top\s*sách|top\s*sach)\b", text, re.I))


def _is_new_books_question(text: str) -> bool:
    return bool(re.search(r"\b(sách mới|sach moi|mới nhất|moi nhat|new\s*arrivals|new books|vừa ra mắt|vua ra mat)\b", text, re.I))


def _is_same_author_question(text: str) -> bool:
    return bool(re.search(r"\b(cùng tác giả|cung tac gia|same author|của tác giả|cua tac gia|author)\b", text, re.I))


def _extract_book_titles_for_compare(text: str) -> list[str]:
    # Examples: "Dune va Cosmos cuon nao re hon", "so sanh gia Clean Code va Dune"
    m = re.search(
        r"([A-ZÀ-Ỹa-zà-ỹ0-9][A-ZÀ-Ỹa-zà-ỹ0-9\s\-\+\.#]{1,60}?)\s+(?:và|va|vs|với|voi)\s+([A-ZÀ-Ỹa-zà-ỹ0-9][A-ZÀ-Ỹa-zà-ỹ0-9\s\-\+\.#]{1,60})",
        text,
        re.I,
    )
    if not m:
        # Fallback for comma-separated compare prompts: "Dune, Cosmos cuốn nào rẻ hơn"
        m = re.search(
            r"([A-ZÀ-Ỹa-zà-ỹ0-9][A-ZÀ-Ỹa-zà-ỹ0-9\s\-\+\.#]{1,60})\s*,\s*([A-ZÀ-Ỹa-zà-ỹ0-9][A-ZÀ-Ỹa-zà-ỹ0-9\s\-\+\.#]{1,60})",
            text,
            re.I,
        )
    if not m:
        return []

    noise = r"\b(cuon|cuốn|quyen|quyển|sach|sách|nao|nào|re|rẻ|dat|đắt|hon|hơn|gia|giá|bao|nhieu|nhiêu|tien|tiền|co|có|khong|không|so\s+sanh|sánh)\b"
    t1 = re.sub(noise, " ", m.group(1), flags=re.I).strip(" .,!?:;\"'()[]")
    t2 = re.sub(noise, " ", m.group(2), flags=re.I).strip(" .,!?:;\"'()[]")
    # Remove common trailing question tails that can cling to 2nd title.
    t2 = re.sub(r"\b(cuốn|cuon|quyển|quyen)?\s*(nào|nao)?\s*(rẻ|re|đắt|dat)?\s*(hơn|hon)?\s*$", "", t2, flags=re.I).strip(" .,!?:;\"'()[]")
    t1 = re.sub(r"\s+", " ", t1)
    t2 = re.sub(r"\s+", " ", t2)
    out = []
    for t in (t1, t2):
        if len(t) >= 2 and t.lower() not in {"nào", "nao"}:
            out.append(t)
    return out[:2]


def _extract_book_title(text: str) -> str | None:
    quoted = re.search(r"[\"']([^\"']{2,80})[\"']", text)
    if quoted:
        q = quoted.group(1).strip()
        if len(q) >= 2:
            return q

    # Examples: "mua cuon Romeo", "tim quyen Clean Code"
    m = re.search(
        r"(?:cuốn|cuon|quyển|quyen|tựa|tua|tên|ten)\s+([A-ZÀ-Ỹa-zà-ỹ0-9][A-ZÀ-Ỹa-zà-ỹ0-9\s\-\+\.#]{1,60})",
        text,
        re.I,
    )
    if not m:
        return None
    title = m.group(1).strip(" .,!?:;\"'()[]")
    if len(title) < 2:
        return None
    first_word = title.split()[0].lower() if title.split() else ""
    if first_word in {"nao", "nào", "gi", "gì", "bao", "co", "có", "con", "còn"}:
        return None
    lowered = title.lower()
    if re.search(r"\b(gia|giá|tot|tốt|nhat|nhất|hang|khong|không|bao\s+nhieu)\b", lowered, re.I):
        return None
    return title


def _extract_product_keywords(
    text: str,
    category: str | None,
    brand: str | None = None,
    product_type: str | None = None,
    product_name: str | None = None,
) -> list[str]:
    """Extract meaningful product search keywords."""
    # Remove common stop words
    stopwords = {
        "tìm", "tim", "kiếm", "kiem",
        "tôi", "toi", "bạn", "ban", "cho", "của", "cua", "và", "va",
        "là", "la", "có", "co", "được", "duoc", "với", "voi", "trong",
        "the", "a", "an", "is", "are", "to", "for", "me", "my", "i",
        "gợi", "goi", "ý", "y", "sách", "sach", "book", "books",
        "muốn", "muon", "cần", "can", "mua", "buy", "cuốn", "cuon", "quyển", "quyen",
    }
    words = re.findall(r"\b\w{3,}\b", text.lower())
    keywords = [w for w in words if w not in stopwords]
    # Deduplicate while preserving order
    seen: set[str] = set()
    result = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            result.append(w)

    # Seed concrete product title terms to improve retrieval precision.
    if product_name:
        for token in re.findall(r"\b\w{3,}\b", product_name.lower()):
            if token not in stopwords and token not in seen:
                seen.add(token)
                result.insert(0, token)

    # Preserve actionable fallback keyword for broad shopping asks like "mua gì đó".
    text_lower = text.lower()
    if not result and ("mua" in text_lower or "buy" in text_lower):
        result.append("mua")

    # Prefer specific domain tokens first so response hints include expected words.
    priority = ["python", "lập", "trình", "lap", "trinh", "giá", "gia", "rẻ", "re", "đắt", "dat", "còn", "con", "hàng", "hang", "laptop", "phone", "mobile", "tablet", "camera", "printer", "router", "webcam"]
    result.sort(key=lambda w: (0 if w in priority else 1, priority.index(w) if w in priority else 999, len(w)))
    # If no meaningful token is left, keep structured entities as fallback hints.
    if not result:
        for token in (category, brand, product_type):
            if token:
                result.append(str(token))

    return result[:10]


def extract(message: str, intent: str) -> dict[str, Any]:
    """
    Extract entities from message given detected intent.
    Returns a dict of entity_name → value.
    """
    text = message.strip()
    entities: dict[str, Any] = {}

    budget_min, budget_max = _extract_budget(text)
    if budget_min is not None:
        entities["budget_min"] = budget_min
    if budget_max is not None:
        entities["budget_max"] = budget_max

    category = _extract_category(text)
    if category:
        entities["category"] = category

    brand = _extract_brand(text)
    if brand:
        entities["brand"] = brand

    product_type = _extract_product_type(text)
    if product_type:
        entities["product_type"] = product_type

    specific_product = _extract_specific_product(text)
    if specific_product:
        entities["product_name"] = specific_product
        entities.setdefault("book_title", specific_product)

    if _is_price_question(text):
        entities["ask_price"] = True

    if _is_stock_question(text):
        entities["ask_stock"] = True

    if _is_best_price_question(text):
        entities["ask_best_price"] = True

    if _is_compare_price_question(text):
        entities["ask_compare_price"] = True

    if _is_next_book_question(text):
        entities["ask_next_book"] = True

    if _is_bestseller_question(text):
        entities["ask_bestseller"] = True

    if _is_new_books_question(text):
        entities["ask_new_books"] = True

    if _is_same_author_question(text):
        entities["ask_same_author"] = True

    if intent in ("order_support",):
        order_id = _extract_order_id(text)
        if order_id:
            entities["order_id"] = order_id

    policy_topic = _extract_policy_topic(text)
    if policy_topic:
        entities["policy_topic"] = policy_topic

    rating = _extract_rating_threshold(text)
    if rating:
        entities["rating_threshold"] = rating

    author = _extract_author(text)
    if author:
        entities["author"] = author

    book_title = _extract_book_title(text)
    if book_title:
        entities["book_title"] = book_title

    compare_titles = _extract_book_titles_for_compare(text)
    if len(compare_titles) >= 2:
        entities["book_titles"] = compare_titles
        if "book_title" not in entities:
            entities["book_title"] = compare_titles[0]

    keywords = _extract_product_keywords(
        text,
        category,
        brand=brand,
        product_type=product_type,
        product_name=entities.get("book_title") or entities.get("product_name"),
    )
    if keywords:
        entities["product_keywords"] = keywords
    elif category or brand or product_type:
        fallback_terms = [t for t in (category, brand, product_type) if t]
        if fallback_terms:
            entities["product_keywords"] = fallback_terms

    logger.debug("Entities extracted: %s", entities)
    return entities
