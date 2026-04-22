"""
ResponseComposer
─────────────────
Composes final chatbot responses per intent.
Each handler receives structured data and returns a human-readable answer.
All text is generated from data — no hardcoded product lists.
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _variant(options: list[str], key: str = "") -> str:
    """Deterministic phrase variation to keep responses natural without randomness."""
    if not options:
        return ""
    idx = abs(hash(key or "default")) % len(options)
    return options[idx]


def _closing_prompt(key: str = "") -> str:
    return _variant(
        [
            "Nếu bạn muốn, mình lọc tiếp theo giá, thương hiệu hoặc mức còn hàng nha.",
            "Mình có thể đi tiếp theo ngân sách, danh mục hoặc gu bạn hay xem nữa.",
            "Muốn chốt nhanh hơn thì mình rút gọn thêm theo nhu cầu của bạn luôn.",
        ],
        key,
    )


def _behavior_line(data: dict[str, Any]) -> str:
    profile = data.get("behavior_profile") or {}
    segment = str(profile.get("customer_segment", "") or "").lower()
    categories = [str(item.get("category", "")).strip() for item in profile.get("preferred_categories", []) if isinstance(item, dict) and item.get("category")]
    categories = [cat for cat in categories if cat]

    if categories:
        return f"Mình thấy bạn hay để ý {', '.join(categories[:2])}, nên mình sẽ ưu tiên gợi ý đúng gu hơn cho bạn."
    if segment in {"champion", "loyal"}:
        return "Mình đi thẳng vào vài lựa chọn sát nhu cầu của bạn nhé."
    if segment in {"engaged", "casual"}:
        return "Mình sẽ bám theo những gì bạn vừa xem để lọc sát hơn nha."
    return "Mình sẽ cố trả lời sát hơn với đúng điều bạn đang hỏi."


def _history_line(data: dict[str, Any]) -> str:
    history = data.get("history") or []
    if not history:
        return ""

    has_user = False
    has_assistant = False
    for item in reversed(history):
        role = str(item.get("role", ""))
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        if role == "assistant":
            has_assistant = True
        elif role == "user":
            has_user = True
        if has_user and has_assistant:
            break

    if has_user and has_assistant:
        return "Mình đang nối tiếp ý trước của bạn nên sẽ giữ ngữ cảnh cho mượt nha."
    if has_user:
        return "Mình sẽ bám sát câu hỏi gần nhất để trả lời gọn hơn nhé."
    return ""


def _normalize_branding_text(text: str) -> str:
    if not text:
        return ""

    normalized = str(text)
    replacements = [
        ("nhà sách trực tuyến", "nền tảng thương mại điện tử"),
        ("Tìm sách bạn muốn mua", "Tìm sản phẩm bạn muốn mua"),
        ("mua sách", "mua sản phẩm"),
    ]
    for old, new in replacements:
        normalized = normalized.replace(old, new)
    return normalized


def _fmt_price(p: float) -> str:
    return f"{int(p):,}đ"


def _friendly_reason(raw_reason: str) -> str:
    if not raw_reason:
        return "Phù hợp với nhu cầu gần đây của bạn"

    text = str(raw_reason).strip()
    if not text:
        return "Phù hợp với nhu cầu gần đây của bạn"

    # Keep only the first meaningful hint and hide internal model jargon.
    first = text.split("|")[0].split(";")[0].strip()
    lower = first.lower()

    if "thể loại" in lower:
        return first.replace("behavior:", "").replace("graph:", "").strip()
    if "cùng brand" in lower or "thương hiệu" in lower:
        return "Cùng thương hiệu bạn thường quan tâm"
    if "cùng loại sản phẩm" in lower:
        return "Cùng loại sản phẩm bạn đang xem gần đây"
    if "phổ biến" in lower or "bán chạy" in lower:
        return "Được nhiều khách hàng quan tâm gần đây"
    if "lstm" in lower or "graph" in lower or "behavior" in lower or "rag" in lower:
        return "Phù hợp với hành vi mua sắm gần đây của bạn"

    cleaned = first
    for token in ("behavior:", "graph:", "lstm:", "popularity:", "RAG:"):
        cleaned = cleaned.replace(token, "")
    cleaned = cleaned.strip()
    return cleaned or "Phù hợp với nhu cầu gần đây của bạn"


def _fmt_book(b: dict) -> str:
    title  = b.get("title", "N/A")
    author = b.get("author", "")
    price  = float(b.get("price", 0))
    cat    = b.get("category", "")
    rating = b.get("avg_rating", 0)
    reason = _friendly_reason(str(b.get("reason", "") or ""))
    lines = [f"- {title}"]
    if author:
        lines.append(f"  Tác giả: {author}")
    if cat:
        lines.append(f"  Danh mục: {cat}")
    lines.append(f"  Giá: {_fmt_price(price)}")
    if rating:
        lines.append(f"  Đánh giá: {rating:.1f}")
    if reason:
        lines.append(f"  Gợi ý: {reason}")
    return "\n".join(lines)


def compose(
    intent: str,
    entities: dict[str, Any],
    data: dict[str, Any],
    customer_id: int | None = None,
) -> str:
    """
    Route to the correct composer based on intent.
    data contains pre-fetched structured data from services.
    """
    composers = {
        "greeting":         _compose_greeting,
        "faq":              _compose_faq,
        "return_policy":    _compose_return_policy,
        "payment_support":  _compose_payment_support,
        "shipping_support": _compose_shipping_support,
        "product_advice":   _compose_product_advice,
        "order_support":    _compose_order_support,
        "general_search":   _compose_general_search,
        "fallback":         _compose_fallback,
    }
    fn = composers.get(intent, _compose_fallback)
    return fn(entities, data, customer_id)


def _compose_greeting(entities: dict, data: dict, customer_id: int | None) -> str:
    key = f"greeting:{customer_id or 0}"
    opener = _variant(
        [
            "Mình ở Ecommerce đây, có gì cứ hỏi mình nhé.",
            "Chào bạn! Mình ở đây để giúp bạn tìm đúng thứ đang cần nè.",
            "Hello! Mình sẵn sàng hỗ trợ bạn từ gợi ý đến tra cứu đơn hàng luôn.",
        ],
        key,
    )
    return (
        f"Xin chào! {opener}\n\n"
        f"{_behavior_line(data)}\n\n"
        f"{_history_line(data)}\n\n"
        "Bạn có thể nhắn nhanh kiểu này:\n"
        "• Gợi ý sản phẩm phù hợp cho tôi\n"
        "• Tìm laptop dưới 20 triệu\n"
        "• Đơn hàng của tôi"
    )


def _compose_faq(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    if not sources:
        return (
            "Tôi chưa tìm thấy thông tin phù hợp trong cơ sở dữ liệu. "
            "Vui lòng liên hệ support@ecommerce.vn để được hỗ trợ! 📧"
        )
    top = sources[0]
    answer = f"**{_normalize_branding_text(top['title'])}**\n\n{_normalize_branding_text(top['content'])}"
    if len(sources) > 1:
        answer += f"\n\n---\n💡 Xem thêm: **{_normalize_branding_text(sources[1]['title'])}**"
    return answer


def _compose_return_policy(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    if sources:
        top = sources[0]
        return f"**Chính sách đổi trả Ecommerce**\n\n{_normalize_branding_text(top['content'])}"
    return (
        "**Chính sách đổi trả Ecommerce**\n\n"
        "Ecommerce chấp nhận đổi trả trong vòng 7 ngày kể từ ngày nhận hàng.\n"
        "Điều kiện: sản phẩm còn nguyên vẹn, chưa qua sử dụng.\n"
        "Liên hệ: support@ecommerce.vn hoặc hotline 1800-xxxx."
    )


def _compose_payment_support(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    if sources:
        top = sources[0]
        return f"**Thanh toán tại Ecommerce**\n\n{_normalize_branding_text(top['content'])}"
    return (
        "**Phương thức thanh toán Ecommerce**\n\n"
        "• 💳 Thẻ tín dụng/ghi nợ (Visa, Mastercard)\n"
        "• 💵 COD — Thanh toán khi nhận hàng\n"
        "• 🏦 Chuyển khoản ngân hàng\n"
        "Tất cả giao dịch được mã hóa SSL."
    )


def _compose_shipping_support(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    if sources:
        top = sources[0]
        return f"**Giao hàng tại Ecommerce**\n\n{_normalize_branding_text(top['content'])}"
    return (
        "**Thông tin giao hàng Ecommerce**\n\n"
        "• 📦 Giao hàng tiêu chuẩn: 3–5 ngày làm việc\n"
        "• ⚡ Giao hàng nhanh: 1–2 ngày (phụ phí)\n"
        "• 🎁 Miễn phí ship cho đơn từ 300.000đ\n"
        "Theo dõi đơn hàng trong mục 'Đơn hàng của tôi'."
    )


def _compose_product_advice(entities: dict, data: dict, customer_id: int | None) -> str:
    recs = data.get("recommendations", [])
    budget_max = entities.get("budget_max")
    category   = entities.get("category")
    keywords   = entities.get("product_keywords", [])
    not_found_title = data.get("not_found_title")
    behavior_profile = data.get("behavior_profile") or {}
    behavior_hint = _behavior_line(data)
    history_hint = _history_line(data)

    if not recs:
        if not_found_title:
            return (
                f"Mình chưa tìm thấy sản phẩm '{not_found_title}' trong kho hiện tại. "
                "Bạn thử thêm tên đầy đủ, thương hiệu hoặc danh mục để mình lọc chính xác hơn nha."
            )
        context = data.get("rag_context", "")
        if context:
            return f"Mình có chút thông tin liên quan đây:\n\n{context}\n\nBạn muốn mình đào sâu thêm sản phẩm nào nữa không?"
        return (
            "Mình chưa tìm ra sản phẩm khớp với yêu cầu này. "
            f"{history_hint} {behavior_hint} Bạn thử mô tả rõ hơn về danh mục, mức giá hoặc thương hiệu quan tâm nhé."
        )

    lines = ["Mình gợi ý vài lựa chọn hợp với bạn nè:", behavior_hint]
    if history_hint:
        lines.append(history_hint)
    lines.append("")

    for i, b in enumerate(recs[:5], start=1):
        lines.append(f"Sản phẩm {i}")
        lines.append(_fmt_book(b))
        lines.append("")

    # Keep the ending short so the list stays visually airy.
    lines.append("Bạn muốn lọc thêm theo giá, thương hiệu hay tồn kho?")
    return "\n".join(lines)


def _compose_order_support(entities: dict, data: dict, customer_id: int | None) -> str:
    order_data = data.get("order_data", {})

    if not order_data.get("found"):
        return order_data.get("message", "Không tìm thấy thông tin đơn hàng.")

    # Single order detail
    if "order_id" in order_data:
        o = order_data
        lines = [
            f"📦 **Đơn hàng #{o['order_id']}**",
            f"Trạng thái: {o['status']}",
            f"Tổng tiền: {_fmt_price(o['total'])}",
            f"Ngày đặt: {o['created']}",
        ]
        if o.get("address"):
            lines.append(f"Địa chỉ: {o['address']}")
        ship = o.get("shipping", {})
        if ship.get("status"):
            lines.append(f"\n🚚 **Vận chuyển**: {ship['status']}")
            if ship.get("tracking"):
                lines.append(f"Mã tracking: {ship['tracking']}")
            if ship.get("eta"):
                lines.append(f"Dự kiến giao: {ship['eta']}")
        pay = o.get("payment", {})
        if pay.get("status"):
            lines.append(f"\n💳 **Thanh toán**: {pay['status']}")
            if pay.get("method"):
                lines.append(f"Phương thức: {pay['method']}")
        return "\n".join(lines)

    # List of orders
    orders = order_data.get("orders", [])
    lines  = [f"📦 **{order_data['count']} đơn hàng gần đây của bạn:**", ""]
    for o in orders:
        lines.append(
            f"• Đơn #{o['order_id']} | {o['status']} | "
            f"{_fmt_price(o['total'])} | {o['items']} sản phẩm | {o['created']}"
        )
    lines.append("\nNhập mã đơn hàng để xem chi tiết (ví dụ: 'đơn hàng #123')")
    return "\n".join(lines)


def _compose_general_search(entities: dict, data: dict, customer_id: int | None) -> str:
    recs    = data.get("recommendations", [])
    sources = data.get("sources", [])
    keywords = entities.get("product_keywords", [])
    ask_price = entities.get("ask_price", False)
    ask_stock = entities.get("ask_stock", False)
    ask_best_price = entities.get("ask_best_price", False)
    ask_compare_price = entities.get("ask_compare_price", False)
    ask_next_book = entities.get("ask_next_book", False)
    ask_bestseller = entities.get("ask_bestseller", False)
    ask_new_books = entities.get("ask_new_books", False)
    ask_same_author = entities.get("ask_same_author", False)
    book_title = entities.get("book_title")
    book_titles = entities.get("book_titles", [])
    resolved_author = data.get("resolved_author")
    history_hint = _history_line(data)

    if recs:
        style_key = f"search:{customer_id}:{book_title or ''}:{','.join(keywords[:3])}"
        behavior_hint = _behavior_line(data)
        if ask_compare_price:
            if len(recs) >= 2:
                sorted_by_price = sorted(recs, key=lambda x: float(x.get("price", 0) or 0))
                cheapest = sorted_by_price[0]
                expensive = sorted_by_price[-1]
                lines = ["⚖️ **Mình so sánh giá giúp bạn nè**"]
                if history_hint:
                    lines.append(history_hint)
                lines.append(behavior_hint)
                for b in sorted_by_price[:4]:
                    lines.append(f"• **{b.get('title', 'Sản phẩm')}**: {_fmt_price(float(b.get('price', 0) or 0))}")
                lines.append("")
                lines.append(f"✅ Rẻ hơn: **{cheapest.get('title', 'Sản phẩm')}**")
                lines.append(f"💸 Đắt hơn: **{expensive.get('title', 'Sản phẩm')}**")
                lines.append("")
                lines.append(_closing_prompt(style_key))
                return "\n".join(lines)

            if len(recs) == 1:
                only = recs[0]
                expected = ", ".join(book_titles[:2]) if book_titles else "2 sản phẩm"
                return (
                    "⚠️ **Mình chưa đủ dữ liệu để so sánh giá**\n"
                    f"Mình mới tìm thấy 1 sản phẩm trong yêu cầu ({expected}):\n"
                    f"• **{only.get('title', 'Sản phẩm')}**: {_fmt_price(float(only.get('price', 0) or 0))}\n"
                    "Bạn kiểm tra lại tên sản phẩm còn lại giúp mình nha."
                )

            expected = ", ".join(book_titles[:2]) if book_titles else "2 sản phẩm"
            return (
                "⚠️ **Mình chưa tìm thấy dữ liệu để so sánh giá**\n"
                f"Yêu cầu: {expected}.\n"
                "Bạn thử nhập đúng tên sản phẩm hoặc đặt trong dấu nháy, ví dụ: \"Dune\" và \"Cosmos\" nhé."
            )

        if ask_best_price:
            sorted_by_price = sorted(recs, key=lambda x: float(x.get("price", 0) or 0))
            best = sorted_by_price[0]
            lines = ["💸 **Mình tìm ra món giá tốt nhất hiện tại nè**"]
            if history_hint:
                lines.append(history_hint)
            lines.extend([
                behavior_hint,
                f"📘 **{best.get('title', 'Sản phẩm')}** — {_fmt_price(float(best.get('price', 0) or 0))}",
            ])
            if isinstance(best.get("stock"), int):
                stock = int(best.get("stock", 0) or 0)
                lines.append("✅ Còn hàng" if stock > 0 else "⚠️ Tạm hết hàng")

            if len(sorted_by_price) > 1:
                lines.append("\nMột vài lựa chọn giá tốt khác:")
                for b in sorted_by_price[1:3]:
                    lines.append(f"• {b.get('title', 'Sản phẩm')} — {_fmt_price(float(b.get('price', 0) or 0))}")
            lines.append("")
            lines.append(_closing_prompt(style_key))
            return "\n".join(lines)

        if ask_stock:
            lines = []
            if history_hint:
                lines.append(history_hint)
            lines.append(behavior_hint)
            for b in recs[:3]:
                raw_stock = b.get("stock")
                if raw_stock is None:
                    status = "ℹ️ Mình chưa có dữ liệu tồn kho"
                else:
                    stock = int(raw_stock or 0)
                    status = f"✅ Còn {stock} sản phẩm" if stock > 0 else "⚠️ Tạm hết hàng"
                lines.append(f"📦 **{b.get('title', 'Sản phẩm')}**: {status}")
            if book_title and lines:
                lines.insert(0, f"Tình trạng kho cho '{book_title}':")
            lines.append("")
            lines.append(_closing_prompt(style_key))
            return "\n".join(lines)

        if ask_price:
            if entities.get("budget_min") is not None or entities.get("budget_max") is not None:
                bmin = entities.get("budget_min")
                bmax = entities.get("budget_max")
                range_desc = ""
                if bmin is not None and bmax is not None:
                    range_desc = f" (từ {_fmt_price(float(bmin))} đến {_fmt_price(float(bmax))})"
                elif bmax is not None:
                    range_desc = f" (dưới {_fmt_price(float(bmax))})"
                elif bmin is not None:
                    range_desc = f" (trên {_fmt_price(float(bmin))})"
                lines = [f"💰 **Mấy sản phẩm trong tầm giá bạn yêu cầu{range_desc}**"]
                if history_hint:
                    lines.append(history_hint)
                lines.append(behavior_hint)
                for b in sorted(recs[:5], key=lambda x: float(x.get("price", 0) or 0)):
                    lines.append(
                        f"• **{b.get('title', 'Sản phẩm')}**: {_fmt_price(float(b.get('price', 0) or 0))}"
                    )
                return "\n".join(lines)

            lines = []
            for b in recs[:3]:
                lines.append(
                    f"💰 **{b.get('title', 'Sản phẩm')}** hiện đang ở mức {_fmt_price(float(b.get('price', 0) or 0))}"
                )
            if book_title and lines:
                lines.insert(0, f"Thông tin giá cho '{book_title}':")
            lines.append("")
            lines.append(_closing_prompt(style_key))
            return "\n".join(lines)

        if ask_next_book:
            lines = ["📚 **Nếu muốn xem tiếp thì mấy món này khá hợp nè**"]
            if history_hint:
                lines.append(history_hint)
            lines.extend([behavior_hint, ""])
            for b in recs[:5]:
                lines.append(_fmt_book(b))
                lines.append("")
            lines.append(_closing_prompt(style_key))
            return "\n".join(lines)

        if ask_bestseller:
            lines = ["🔥 **Mấy món đang được quan tâm nhiều nè**"]
            if history_hint:
                lines.append(history_hint)
            lines.extend([behavior_hint, ""])
            for b in recs[:5]:
                lines.append(_fmt_book(b))
                lines.append("")
            lines.append(_closing_prompt(style_key))
            return "\n".join(lines)

        if ask_new_books:
            lines = ["🆕 **Mấy sản phẩm mới lên kệ nè**"]
            if history_hint:
                lines.append(history_hint)
            lines.extend([behavior_hint, ""])
            for b in recs[:5]:
                lines.append(_fmt_book(b))
                lines.append("")
            lines.append(_closing_prompt(style_key))
            return "\n".join(lines)

        if ask_same_author:
            head = f"✍️ **Mấy sản phẩm cùng tác giả {resolved_author}**" if resolved_author else "✍️ **Mấy sản phẩm cùng tác giả**"
            lines = [head]
            if history_hint:
                lines.append(history_hint)
            lines.extend([behavior_hint, ""])
            for b in recs[:6]:
                lines.append(_fmt_book(b))
                lines.append("")
            lines.append(_closing_prompt(style_key))
            return "\n".join(lines)

        kw_str = ", ".join(keywords[:3]) if keywords else "từ khóa của bạn"
        search_lead = _variant(
            [
                f"🔍 **Mình tìm được vài kết quả theo '{kw_str}'**",
                f"🔎 **Dưới đây là các món liên quan đến '{kw_str}'**",
                f"📌 **Mấy lựa chọn khớp với '{kw_str}'**",
            ],
            style_key,
        )
        lines  = [search_lead]
        if history_hint:
            lines.append(history_hint)
        lines.extend([behavior_hint, ""])
        for b in recs[:5]:
            lines.append(_fmt_book(b))
            lines.append("")
        lines.append(_closing_prompt(style_key))
        return "\n".join(lines)

    if sources:
        return f"🔍 **Mình tìm được thông tin này:**\n\n{_normalize_branding_text(sources[0]['content'])}"

    if ask_stock and book_title:
        return f"Mình chưa thấy dữ liệu tồn kho cho '{book_title}' lúc này. Bạn thử lại sau ít phút nha."
    if ask_stock:
        return "Hiện mình chưa lấy được danh sách còn hàng theo yêu cầu. Bạn có thể nêu tên sản phẩm để mình kiểm tra kỹ hơn nhé."
    if ask_best_price:
        return "Hiện mình chưa đủ dữ liệu để chốt mức giá tốt nhất. Bạn thử nêu danh mục hoặc khoảng giá để mình lọc nhanh hơn nhé."
    if ask_compare_price:
        return "Mình chưa đủ dữ liệu để so sánh giá. Bạn thử nêu 2 sản phẩm cụ thể hoặc hỏi kiểu 'sản phẩm nào rẻ hơn' nhé."
    if ask_next_book:
        return "Mình chưa có đủ ngữ cảnh để gợi ý sản phẩm tiếp theo. Bạn có thể nêu món bạn vừa xem hoặc đang quan tâm nhé."
    if ask_same_author:
        return "Mình chưa tìm thấy sản phẩm cùng tác giả theo yêu cầu. Bạn thử cho mình tên tác giả cụ thể nha."
    if ask_price:
        bmin = entities.get("budget_min")
        bmax = entities.get("budget_max")
        if bmin is not None and bmax is not None:
            return f"Mình chưa tìm thấy sản phẩm trong khoảng {_fmt_price(float(bmin))} - {_fmt_price(float(bmax))}. Bạn thử nới rộng khoảng giá nha."
        if bmin is not None:
            return f"Mình chưa tìm thấy sản phẩm có giá từ {_fmt_price(float(bmin))} trở lên trong dữ liệu hiện tại."
        if bmax is not None:
            return f"Mình chưa tìm thấy sản phẩm có giá dưới {_fmt_price(float(bmax))} trong dữ liệu hiện tại."
        return "Mình chưa tìm thấy thông tin giá theo yêu cầu của bạn."
    if ask_bestseller:
        return "Hiện chưa đủ dữ liệu để xếp hạng sản phẩm bán chạy. Bạn thử lại sau khi có thêm lượt mua hoặc đánh giá nhé."
    if ask_new_books:
        return "Hiện chưa có dữ liệu sản phẩm mới trong kho. Bạn thử lại sau nhé."

    kw_str = ", ".join(keywords[:3]) if keywords else "từ khóa"
    return (
        f"Mình chưa tìm ra kết quả cho '{kw_str}'. "
        "Bạn thử đổi từ khóa khác hoặc nói rõ hơn về danh mục bạn quan tâm nhé. 🔍"
    )


def _compose_fallback(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    if sources:
        key = f"fallback:{customer_id}:{sources[0].get('title','')}"
        preface = _variant(
            [
                "Mình tìm thấy nội dung có thể hữu ích cho câu hỏi của bạn:",
                "Có một thông tin khá gần với yêu cầu bạn đang hỏi:",
                "Đây là phần thông tin liên quan nhất mình truy xuất được:",
            ],
            key,
        )
        return (
            f"{preface}\n\n"
            f"**{_normalize_branding_text(sources[0]['title'])}**\n{_normalize_branding_text(sources[0]['content'])}\n\n"
            f"{_history_line(data)}\n"
            f"{_behavior_line(data)}\n\n"
            f"{_closing_prompt(key)}"
        )
    return (
        "Mình chưa hiểu rõ ý bạn lắm. 🤔\n\n"
        "Mình có thể giúp bạn theo mấy hướng này:\n"
        "• 💡 **Gợi ý sản phẩm** — 'Gợi ý sản phẩm phù hợp cho tôi'\n"
        "• 🔍 **Tìm sản phẩm** — 'Tìm sản phẩm của thương hiệu X'\n"
        "• 📦 **Đơn hàng** — 'Đơn hàng của tôi'\n"
        "• 🔄 **Đổi trả** — 'Chính sách đổi trả'\n"
        "• 💳 **Thanh toán** — 'Phương thức thanh toán'"
    )
