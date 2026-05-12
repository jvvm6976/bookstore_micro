"""
Intent Detector
───────────────
Multi-signal intent detection với confidence scoring.
Không dùng external LLM — hoàn toàn offline.

Signals:
  1. Keyword patterns (weighted)
  2. Context từ conversation history
  3. Confidence threshold để fallback

Intents:
  greeting        – chào hỏi
  recommend       – gợi ý sách
  book_search     – tìm sách
  book_detail     – chi tiết sách cụ thể
  order_status    – tra cứu đơn hàng
  order_detail    – chi tiết đơn hàng cụ thể
  faq_return      – chính sách đổi trả
  faq_payment     – phương thức thanh toán
  faq_shipping    – thời gian/phí giao hàng
  faq_account     – tài khoản / đăng ký
  faq_general     – FAQ chung
  explain_rec     – giải thích tại sao gợi ý
  fallback        – không nhận ra
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.25


@dataclass
class IntentResult:
    intent: str
    confidence: float
    signals: list[str]


# ── Weighted keyword rules ────────────────────────────────────────────────────
# Format: (intent, weight, patterns)
# Higher weight = stronger signal

RULES: list[tuple[str, float, list[str]]] = [
    # Greeting
    ('greeting', 1.0, [
        r'\b(xin chao|hello|hi|chao|hey|xinchao|good morning|good afternoon)\b',
        r'^(chao|hi|hello|hey)\s*[!.]*$',
    ]),

    # Recommend
    ('recommend', 1.0, [
        r'\b(goi y|recommend|de xuat|nen mua|mua gi|sach hay|sach nao|suggest|tu van)\b',
        r'\b(sach phu hop|sach tot|nen doc|nen mua gi|mua sach gi)\b',
        r'\b(cho toi biet|gioi thieu|tim sach hay)\b',
    ]),

    # Book search
    ('book_search', 0.9, [
        r'\b(tim kiem|tim sach|search|co sach|sach ve|sach cua|sach nao co)\b',
        r'\b(ban co|shop co|co ban|co cuon)\b',
        r'\b(sach (lap trinh|khoa hoc|lich su|toan|tieu thuyet|van hoc))\b',
    ]),

    # Book detail
    ('book_detail', 0.9, [
        r'\b(chi tiet|thong tin|gia bao nhieu|mo ta|tac gia la|xuat ban|nha xuat ban)\b',
        r'\b(cuon sach|quyen sach|book) .{2,30} (la gi|nhu the nao|bao nhieu)\b',
        r'\b(gia cua|gia sach|bao nhieu tien|con hang khong|con trong kho)\b',
    ]),

    # Order status
    ('order_status', 1.0, [
        r'\b(don hang|order|theo doi|tracking|trang thai don|kiem tra don)\b',
        r'\b(don cua toi|don hang cua toi|xem don|lich su mua)\b',
        r'\b(da dat hang|da mua|da order)\b',
    ]),

    # Order detail (specific order)
    ('order_detail', 1.0, [
        r'\b(don hang? #?\d+|order #?\d+|ma don #?\d+)\b',
        r'#\d{1,6}\b',
        r'\b(don so|ma don hang|don id)\b',
    ]),

    # FAQ - Return policy
    ('faq_return', 1.0, [
        r'\b(doi tra|hoan tien|tra hang|refund|return|doi hang|boi thuong)\b',
        r'\b(chinh sach doi|chinh sach tra|dieu kien doi)\b',
        r'\b(bi loi|hang loi|sach hong|sach bi hu)\b',
    ]),

    # FAQ - Payment
    ('faq_payment', 1.0, [
        r'\b(thanh toan|payment|tra tien|cach tra|phuong thuc thanh toan)\b',
        r'\b(the tin dung|visa|mastercard|cod|chuyen khoan|momo|zalopay)\b',
        r'\b(phi thanh toan|phi giao dich|bao mat thanh toan)\b',
    ]),

    # FAQ - Shipping
    ('faq_shipping', 1.0, [
        r'\b(giao hang|van chuyen|shipping|delivery|phi ship|phi van chuyen)\b',
        r'\b(thoi gian giao|bao lau giao|khi nao nhan|nhan hang)\b',
        r'\b(mien phi ship|free ship|phi giao)\b',
    ]),

    # FAQ - Account
    ('faq_account', 0.9, [
        r'\b(dang ky|tai khoan|account|register|signup|login|dang nhap)\b',
        r'\b(quen mat khau|doi mat khau|reset password|xac thuc)\b',
        r'\b(tao tai khoan|mo tai khoan|kich hoat)\b',
    ]),

    # Explain recommendation
    ('explain_rec', 0.9, [
        r'\b(tai sao goi y|vi sao goi y|ly do goi y|giai thich goi y)\b',
        r'\b(sao lai goi y|sao goi y cuon nay|tai sao nen mua)\b',
        r'\b(co phu hop voi toi khong|phu hop voi so thich)\b',
    ]),
]


def detect(text: str, history: list[dict] = None) -> IntentResult:
    """
    Detect intent from text with confidence scoring.
    Uses history for context-aware detection.
    """
    text_lower = text.lower().strip()
    scores: dict[str, float] = {}

    # Score each rule
    for intent, weight, patterns in RULES:
        for pat in patterns:
            if re.search(pat, text_lower):
                scores[intent] = scores.get(intent, 0) + weight

    # Context boost from history
    if history:
        last_intent = _get_last_intent(history)
        if last_intent:
            # If previous was recommend and user asks "why" → explain_rec
            if last_intent == 'recommend' and re.search(r'\b(tai sao|vi sao|sao|why|ly do)\b', text_lower):
                scores['explain_rec'] = scores.get('explain_rec', 0) + 0.8
            # If previous was order_status and user mentions a number → order_detail
            if last_intent == 'order_status' and re.search(r'\d+', text_lower):
                scores['order_detail'] = scores.get('order_detail', 0) + 0.6

    if not scores:
        return IntentResult('fallback', 0.0, [])

    # Normalize scores
    max_score = max(scores.values())
    best_intent = max(scores, key=scores.get)
    confidence = min(max_score / 2.0, 1.0)  # normalize to [0,1]

    signals = [f"{k}={v:.1f}" for k, v in sorted(scores.items(), key=lambda x: -x[1])[:3]]
    logger.debug("Intent: %s (%.2f) signals=%s", best_intent, confidence, signals)

    if confidence < CONFIDENCE_THRESHOLD:
        return IntentResult('fallback', confidence, signals)

    return IntentResult(best_intent, confidence, signals)


def _get_last_intent(history: list[dict]) -> str | None:
    """Extract last assistant intent from history metadata."""
    for msg in reversed(history):
        if msg.get('role') == 'assistant':
            meta = msg.get('metadata', {})
            if isinstance(meta, dict):
                return meta.get('intent')
    return None
