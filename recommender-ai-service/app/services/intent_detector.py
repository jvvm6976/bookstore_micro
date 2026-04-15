"""
IntentDetector
──────────────
Rule-based intent detection using regex patterns + keyword scoring.
Supports both Vietnamese (UTF-8) and ASCII-transliterated input.

Intents:
  faq | product_advice | order_support | payment_support
  shipping_support | return_policy | general_search | fallback
"""
from __future__ import annotations
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Each entry: (intent, [(pattern, weight)])
# Higher weight = stronger signal
_INTENT_RULES: list[Tuple[str, list[Tuple[str, float]]]] = [
    ("return_policy", [
        (r"\b(đổi trả|doi tra|hoàn tiền|hoan tien|refund|return|trả hàng|tra hang|đổi hàng|doi hang)\b", 3.0),
        (r"\b(chính sách|chinh sach|policy|điều kiện|dieu kien)\b", 1.0),
    ]),
    ("payment_support", [
        (r"\b(thanh toán|thanh toan|payment|pay|trả tiền|tra tien|phương thức|phuong thuc)\b", 3.0),
        (r"\b(thẻ tín dụng|the tin dung|visa|mastercard|cod|chuyển khoản|chuyen khoan|momo|vnpay)\b", 2.5),
        (r"\b(hóa đơn|hoa don|invoice|biên lai|bien lai)\b", 1.5),
    ]),
    ("shipping_support", [
        (r"\b(giao hàng|giao hang|vận chuyển|van chuyen|shipping|delivery|ship)\b", 3.0),
        (r"\b(thời gian|thoi gian|bao lâu|bao lau|khi nào|khi nao|phí ship|phi ship)\b", 1.5),
        (r"\b(địa chỉ|dia chi|address|nơi nhận|noi nhan)\b", 1.0),
    ]),
    ("order_support", [
        (r"\b(đơn hàng|don hang|order|đặt hàng|dat hang|mã đơn|ma don|order_id|#\d+)\b", 3.0),
        (r"\b(theo dõi|theo doi|tracking|trạng thái|trang thai|status|kiểm tra|kiem tra)\b", 2.0),
        (r"\b(hủy đơn|huy don|cancel|chưa nhận|chua nhan|thất lạc|that lac)\b", 2.5),
    ]),
    ("product_advice", [
        (r"\b(gợi ý|goi y|recommend|đề xuất|de xuat|tư vấn|tu van|nên mua|nen mua|mua gì|mua gi)\b", 3.0),
        (r"\b(muốn mua|muon mua|cần mua|can mua)\b", 1.8),
        (r"\b(đọc cuốn nào tiếp|doc cuon nao tiep|mua cuốn nào tiếp|mua cuon nao tiep|next book|đọc tiếp|doc tiep)\b", 2.8),
        (r"\b(giá tốt nhất|gia tot nhat|rẻ nhất|re nhat|cheapest|best price)\b", 3.0),
        (r"\b(rẻ hơn|re hon|đắt hơn|dat hon|so sánh giá|so sanh gia|compare)\b", 2.8),
        (r"\b(còn hàng không|con hang khong|hết hàng|het hang|in stock|available)\b", 2.5),
        (r"\b(bán chạy|ban chay|best\s*seller|popular|sách mới|sach moi|mới nhất|moi nhat|new books|new arrivals)\b", 2.5),
        (r"\b(cùng tác giả|cung tac gia|same author|của tác giả|cua tac gia)\b", 2.3),
        (r"\b(sách hay|sach hay|sách nào|sach nao|sách tốt|sach tot|best book|top sách|top sach)\b", 2.5),
        (r"\b(dưới|duoi|under|budget|giá|gia|price|tầm giá|tam gia)\b", 1.5),
        (r"\b(sách\s+giá\s+(trên|tren|dưới|duoi)|trên\s*\d+\s*(k|nghìn|nghin|đồng|dong|vnd)?|dưới\s*\d+\s*(k|nghìn|nghin|đồng|dong|vnd)?|từ\s*\d+\s*(k|nghìn|nghin)?\s*(đến|den|-)\s*\d+)\b", 3.2),
        (r"\b(sách|sach)\s*(trên|tren|dưới|duoi)\s*\d+\b", 3.3),
        (r"\b(sách|sach)\s*(từ|tu)\s*\d+\s*(đến|den|-)\s*\d+\b", 3.3),
        (r"\b(cho người mới|cho nguoi moi|beginner|người mới bắt đầu|nguoi moi bat dau)\b", 2.0),
    ]),
    ("general_search", [
        (r"\b(tìm|tim|search|tìm kiếm|tim kiem|có sách|co sach|sách về|sach ve|sách của|sach cua)\b", 2.5),
        (r"\b(cuốn|cuon|quyển|quyen|book|title)\b", 1.8),
        (r"\b(muốn mua cuốn|muon mua cuon|muốn mua sách|muon mua sach)\b", 3.0),
        (r"\b(giá tốt nhất|gia tot nhat|rẻ nhất|re nhat|cheapest|best price)\b", 2.8),
        (r"\b(rẻ hơn|re hon|đắt hơn|dat hon|so sánh giá|so sanh gia|compare)\b", 2.8),
        (r"\b(còn hàng không|con hang khong|hết hàng|het hang|in stock|available)\b", 2.3),
        (r"\b(sách\s+giá\s+(trên|tren|dưới|duoi)|trên\s*\d+\s*(k|nghìn|nghin|đồng|dong|vnd)?|dưới\s*\d+\s*(k|nghìn|nghin|đồng|dong|vnd)?|từ\s*\d+\s*(k|nghìn|nghin)?\s*(đến|den|-)\s*\d+)\b", 3.0),
        (r"\b(sách|sach)\s*(trên|tren|dưới|duoi)\s*\d+\b", 3.1),
        (r"\b(sách|sach)\s*(từ|tu)\s*\d+\s*(đến|den|-)\s*\d+\b", 3.1),
        (r"\b(bán chạy|ban chay|best\s*seller|popular|sách mới|sach moi|mới nhất|moi nhat|new books|new arrivals)\b", 2.3),
        (r"\b(cùng tác giả|cung tac gia|same author|của tác giả|cua tac gia)\b", 2.2),
        (r"\b(tác giả|tac gia|author|thể loại|the loai|category|chủ đề|chu de|topic)\b", 1.5),
    ]),
    ("faq", [
        (r"\b(faq|hỏi đáp|hoi dap|câu hỏi|cau hoi|thắc mắc|thac mac|giải đáp|giai dap)\b", 3.0),
        (r"\b(đăng ký|dang ky|register|tài khoản|tai khoan|account|mật khẩu|mat khau|password)\b", 2.0),
        (r"\b(giới thiệu|gioi thieu|about|cloudbooks|moonbooks|nhà sách|nha sach)\b", 1.5),
    ]),
]

# Quick action → intent mapping
QUICK_ACTION_MAP: dict[str, str] = {
    "recommend":       "product_advice",
    "return_policy":   "return_policy",
    "order_support":   "order_support",
    "payment_support": "payment_support",
    "shipping":        "shipping_support",
    "faq":             "faq",
    "search":          "general_search",
}


def detect(message: str, quick_action: str | None = None) -> Tuple[str, float]:
    """
    Returns (intent, confidence_score).
    quick_action overrides detection if provided.
    """
    if quick_action and quick_action in QUICK_ACTION_MAP:
        intent = QUICK_ACTION_MAP[quick_action]
        logger.debug("Intent from quick_action=%s → %s", quick_action, intent)
        return intent, 1.0

    text = message.lower()
    scores: dict[str, float] = {}

    for intent, rules in _INTENT_RULES:
        total = 0.0
        for pattern, weight in rules:
            matches = len(re.findall(pattern, text))
            total += matches * weight
        if total > 0:
            scores[intent] = total

    if not scores:
        return "fallback", 0.0

    best_intent = max(scores, key=lambda k: scores[k])
    confidence  = min(scores[best_intent] / 5.0, 1.0)   # normalize to [0,1]
    logger.debug("Intent scores: %s → best=%s (%.2f)", scores, best_intent, confidence)
    return best_intent, confidence
