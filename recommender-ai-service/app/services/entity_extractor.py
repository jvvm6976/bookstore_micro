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
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Category keyword map (ASCII + Vietnamese)
_CATEGORY_MAP: dict[str, list[str]] = {
    "programming": [
        "lập trình", "lap trinh", "programming", "code", "coding",
        "python", "java", "javascript", "algorithm", "thuật toán", "thuat toan",
        "ai", "machine learning", "deep learning", "data science",
    ],
    "science": [
        "khoa học", "khoa hoc", "science", "vật lý", "vat ly", "hóa học", "hoa hoc",
        "sinh học", "sinh hoc", "biology", "physics", "chemistry",
    ],
    "history": [
        "lịch sử", "lich su", "history", "lịch", "lich", "chiến tranh", "chien tranh",
    ],
    "fiction": [
        "tiểu thuyết", "tieu thuyet", "fiction", "novel", "truyện", "truyen",
        "văn học", "van hoc", "literature",
    ],
    "math": [
        "toán", "toan", "math", "mathematics", "calculus", "algebra", "statistics",
        "xác suất", "xac suat",
    ],
    "business": [
        "kinh doanh", "kinh te", "business", "marketing", "management",
        "quản trị", "quan tri", "khởi nghiệp", "khoi nghiep", "startup",
    ],
    "self_help": [
        "kỹ năng", "ky nang", "self help", "phát triển bản thân", "phat trien ban than",
        "tâm lý", "tam ly", "psychology", "motivation",
    ],
}

# Policy topic map
_POLICY_MAP: dict[str, list[str]] = {
    "return":   ["đổi trả", "doi tra", "hoàn tiền", "hoan tien", "refund", "return"],
    "payment":  ["thanh toán", "thanh toan", "payment", "pay", "thẻ", "the", "cod"],
    "shipping": ["giao hàng", "giao hang", "vận chuyển", "van chuyen", "ship", "delivery"],
    "account":  ["tài khoản", "tai khoan", "account", "đăng ký", "dang ky", "register"],
    "warranty": ["bảo hành", "bao hanh", "warranty", "guarantee"],
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
    m = re.search(r"(?:đơn|don|order|#|mã đơn|ma don)\s*#?\s*(\d+)", text, re.I)
    if m:
        return int(m.group(1))
    # bare number if context is order
    m2 = re.search(r"\b(\d{3,8})\b", text)
    if m2:
        return int(m2.group(1))
    return None


def _extract_category(text: str) -> str | None:
    text_lower = text.lower()
    for cat, keywords in _CATEGORY_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                return cat
    return None


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
    if re.search(r"\b(sách|sach)\s*(trên|tren|dưới|duoi)\s*\d+\b", t, re.I):
        return True
    if re.search(r"\b(sách|sach)\s*(từ|tu)\s*\d+\s*(đến|den|-)\s*\d+\b", t, re.I):
        return True
    if re.search(r"\b(trên|tren|dưới|duoi)\s*\d+\s*(k|nghìn|nghin|đồng|dong|vnd)?\b", t, re.I):
        return True
    if re.search(r"\bgia\b", t) and not re.search(r"\btac\s+gia\b", t):
        return True
    if re.search(r"\b(giá|gia)\s*(dưới|duoi|trên|tren|<|>|từ|tu|đến|den|k|vnd|đồng|dong|\d)", t, re.I):
        return True
    return False


def _is_stock_question(text: str) -> bool:
    return bool(re.search(r"\b(còn hàng không|con hang khong|còn không|con khong|hết hàng chưa|het hang chua|hết hàng không|het hang khong|in stock|available|availability)\b", text, re.I))


def _is_best_price_question(text: str) -> bool:
    return bool(re.search(r"\b(giá\s+tốt\s+nhất|gia\s+tot\s+nhat|rẻ\s+nhất|re\s+nhat|cheapest|best\s+price|giá\s+thấp\s+nhất|gia\s+thap\s+nhat)\b", text, re.I))


def _is_compare_price_question(text: str) -> bool:
    return bool(re.search(r"\b(rẻ hơn|re hon|đắt hơn|dat hon|cao hơn|thấp hơn|thap hon|so sánh giá|so sanh gia|compare|đắt nhất|dat nhat)\b", text, re.I))


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


def _extract_product_keywords(text: str, category: str | None) -> list[str]:
    """Extract meaningful product search keywords."""
    # Remove common stop words
    stopwords = {
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
    return result[:8]


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

    keywords = _extract_product_keywords(text, category)
    if keywords:
        entities["product_keywords"] = keywords

    logger.debug("Entities extracted: %s", entities)
    return entities
