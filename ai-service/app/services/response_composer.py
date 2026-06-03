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


def _fmt_price(p: float) -> str:
    return f"{int(p):,}".replace(",", ".") + "đ"


def _fmt_book(b: dict) -> str:
    title  = b.get("title", "N/A")
    author = b.get("author", "")
    price  = float(b.get("price", 0))
    cat    = b.get("category", "")
    rating = b.get("avg_rating", 0)
    reason = b.get("reason", "")
    line   = f"• **{title}**"
    if author:
        line += f" — {author}"
    if cat:
        line += f" ({cat})"
    line += f"\n  Giá: {_fmt_price(price)}"
    if rating:
        line += f" | Đánh giá: {rating:.1f}/5"
    if reason:
        line += f"\n  Phù hợp vì {reason}."
    return line


def _source_matching(sources: list[dict], keywords: tuple[str, ...]) -> dict | None:
    for source in sources:
        text = f"{source.get('title', '')} {source.get('content', '')}".lower()
        if any(keyword in text for keyword in keywords):
            return source
    return None


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


def _compose_faq(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    if not sources:
        return (
            "Tôi chưa tìm thấy thông tin phù hợp trong cơ sở dữ liệu. "
            "Vui lòng liên hệ support@shopsphere.vn để được hỗ trợ! 📧"
        )
    top = sources[0]
    answer = f"**{top['title']}**\n\n{top['content']}"
    if len(sources) > 1:
        answer += f"\n\n---\n💡 Xem thêm: **{sources[1]['title']}**"
    return answer


def _compose_return_policy(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    top = _source_matching(sources, ("đổi trả", "doi tra", "hoàn tiền", "refund", "return"))
    if top:
        return f"**Chính sách đổi trả ShopSphere**\n\n{top['content']}"
    return (
        "**Chính sách đổi trả ShopSphere**\n\n"
        "ShopSphere chấp nhận đổi trả trong vòng 7 ngày kể từ ngày nhận hàng.\n"
        "Điều kiện: sản phẩm còn nguyên vẹn, chưa qua sử dụng.\n"
        "Liên hệ: support@shopsphere.vn hoặc hotline 1800-xxxx."
    )


def _compose_payment_support(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    top = _source_matching(sources, ("thanh toán", "payment", "cod", "vnpay", "momo", "thẻ"))
    if top:
        return f"**Thanh toán tại ShopSphere**\n\n{top['content']}"
    return (
        "**Phương thức thanh toán ShopSphere**\n\n"
        "• 💳 Thẻ tín dụng/ghi nợ (Visa, Mastercard)\n"
        "• 💵 COD — Thanh toán khi nhận hàng\n"
        "• 🏦 Chuyển khoản ngân hàng\n"
        "Tất cả giao dịch được mã hóa SSL."
    )


def _compose_shipping_support(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    top = _source_matching(sources, ("giao hàng", "vận chuyển", "shipping", "delivery", "tracking", "vận đơn"))
    if top:
        return f"**Giao hàng tại ShopSphere**\n\n{top['content']}"
    return (
        "**Thông tin giao hàng ShopSphere**\n\n"
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

    if not recs:
        if not_found_title:
            return (
                f"Mình chưa tìm thấy sản phẩm tên '{not_found_title}' trong kho hiện tại. "
                "Bạn có thể thử tên đầy đủ hơn hoặc mô tả thêm để tìm chính xác hơn."
            )
        context = data.get("rag_context", "")
        if context:
            return f"Dựa trên thông tin tôi có:\n\n{context}\n\nBạn muốn tìm hiểu thêm về sản phẩm nào?"
        return (
            "Tôi chưa tìm thấy sản phẩm phù hợp với yêu cầu của bạn. "
            "Hãy thử mô tả rõ hơn về thể loại hoặc chủ đề bạn quan tâm! 🛍️"
        )

    header_parts = ["**Gợi ý sản phẩm dành cho bạn**"]
    if category:
        header_parts.append(f"thể loại: {category}")
    if budget_max:
        header_parts.append(f"dưới {_fmt_price(budget_max)}")
    if keywords:
        header_parts.append(f"từ khóa: {', '.join(keywords[:3])}")

    header = " | ".join(header_parts)
    lines  = [header, ""]
    for b in recs[:5]:
        lines.append(_fmt_book(b))
        lines.append("")

    lines.append("Bạn muốn mình lọc tiếp theo mức giá, thương hiệu hoặc nhu cầu sử dụng nào?")

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
        lines.append(f"• Đơn #{o['order_id']} | {o['status']} | "
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

    if recs:
        if ask_compare_price:
            if len(recs) >= 2:
                sorted_by_price = sorted(recs, key=lambda x: float(x.get("price", 0) or 0))
                cheapest = sorted_by_price[0]
                expensive = sorted_by_price[-1]
                lines = ["**So sánh giá sản phẩm**"]
                for b in sorted_by_price[:4]:
                    lines.append(f"• **{b.get('title', 'Sản phẩm')}**: {_fmt_price(float(b.get('price', 0) or 0))}")
                lines.append("")
                lines.append(f"Rẻ hơn: **{cheapest.get('title', 'Sản phẩm')}**")
                lines.append(f"Cao hơn: **{expensive.get('title', 'Sản phẩm')}**")
                return "\n".join(lines)

            if len(recs) == 1:
                only = recs[0]
                expected = ", ".join(book_titles[:2]) if book_titles else "2 sản phẩm"
                return (
                    "**Chưa đủ dữ liệu để so sánh giá**\n"
                    f"Mình mới tìm thấy 1 sản phẩm trong yêu cầu ({expected}):\n"
                    f"• **{only.get('title', 'Sản phẩm')}**: {_fmt_price(float(only.get('price', 0) or 0))}\n"
                    "Bạn kiểm tra lại tên sản phẩm còn lại giúp mình nhé."
                )

            expected = ", ".join(book_titles[:2]) if book_titles else "2 sản phẩm"
            return (
                "**Chưa tìm thấy dữ liệu để so sánh giá**\n"
                f"Yêu cầu: {expected}.\n"
                "Bạn thử nhập đúng tên sản phẩm hoặc đặt trong dấu nháy, ví dụ: \"Dune\" và \"Cosmos\"."
            )

        if ask_best_price:
            sorted_by_price = sorted(recs, key=lambda x: float(x.get("price", 0) or 0))
            best = sorted_by_price[0]
            lines = [
                "**Sản phẩm có giá tốt nhất hiện tại**",
                f"**{best.get('title', 'Sản phẩm')}** — {_fmt_price(float(best.get('price', 0) or 0))}",
            ]
            if isinstance(best.get("stock"), int):
                stock = int(best.get("stock", 0) or 0)
                lines.append("Còn hàng" if stock > 0 else "Tạm hết hàng")

            if len(sorted_by_price) > 1:
                lines.append("\nMột vài lựa chọn giá tốt khác:")
                for b in sorted_by_price[1:3]:
                    lines.append(f"• {b.get('title', 'Sản phẩm')} — {_fmt_price(float(b.get('price', 0) or 0))}")
            return "\n".join(lines)

        if ask_stock:
            stock_recs = recs
            if book_title:
                q = str(book_title).lower()
                exact = [b for b in recs if q in str(b.get("title", "")).lower()]
                stock_recs = exact or recs[:1]
            lines = []
            for b in stock_recs[:3]:
                raw_stock = b.get("stock")
                if raw_stock is None:
                    status = "Chưa có dữ liệu tồn kho"
                else:
                    stock = int(raw_stock or 0)
                    status = f"Còn {stock} sản phẩm" if stock > 0 else "Tạm hết hàng"
                lines.append(f"**{b.get('title', 'Sản phẩm')}**: {status}")
            if book_title and lines:
                lines.insert(0, f"Tình trạng kho cho sản phẩm '{book_title}':")
            return "\n".join(lines)

        if ask_price:
            if entities.get("budget_min") is not None or entities.get("budget_max") is not None:
                lines = ["**Các sản phẩm trong tầm giá bạn yêu cầu**"]
                for b in sorted(recs[:5], key=lambda x: float(x.get("price", 0) or 0)):
                    lines.append(
                        f"• **{b.get('title', 'Sản phẩm')}**: {_fmt_price(float(b.get('price', 0) or 0))}"
                    )
                return "\n".join(lines)

            price_recs = recs
            if book_title:
                q = str(book_title).lower()
                exact = [b for b in recs if q in str(b.get("title", "")).lower()]
                price_recs = exact or recs[:1]
            lines = []
            for b in price_recs[:3]:
                lines.append(
                    f"**{b.get('title', 'Sản phẩm')}** hiện có giá {_fmt_price(float(b.get('price', 0) or 0))}"
                )
            if book_title and lines:
                lines.insert(0, f"Thông tin giá cho sản phẩm '{book_title}':")
            return "\n".join(lines)

        if ask_next_book:
            lines = ["**Bạn có thể xem tiếp các sản phẩm này**", ""]
            for b in recs[:5]:
                lines.append(_fmt_book(b))
                lines.append("")
            return "\n".join(lines)

        if ask_bestseller:
            lines = ["**Sản phẩm bán chạy / phổ biến**", ""]
            for b in recs[:5]:
                lines.append(_fmt_book(b))
                lines.append("")
            return "\n".join(lines)

        if ask_new_books:
            lines = ["**Sản phẩm mới trong kho**", ""]
            for b in recs[:5]:
                lines.append(_fmt_book(b))
                lines.append("")
            return "\n".join(lines)

        if ask_same_author:
            head = f"**Các sản phẩm cùng tác giả {resolved_author}**" if resolved_author else "**Các sản phẩm cùng tác giả**"
            lines = [head, ""]
            for b in recs[:6]:
                lines.append(_fmt_book(b))
                lines.append("")
            return "\n".join(lines)

        kw_str = ", ".join(keywords[:3]) if keywords else "từ khóa của bạn"
        lines  = [f"**Kết quả tìm kiếm: '{kw_str}'**", ""]
        for b in recs[:5]:
            lines.append(_fmt_book(b))
            lines.append("")
        return "\n".join(lines)

    if sources:
        return f"🔍 **Thông tin tìm thấy:**\n\n{sources[0]['content']}"

    if ask_stock and book_title:
        return f"Mình chưa thấy dữ liệu tồn kho cho sản phẩm '{book_title}' lúc này. Bạn thử lại sau ít phút nhé."
    if ask_best_price and book_titles:
        return "Mình chưa tìm được thông tin giá để so sánh giữa các sản phẩm bạn vừa quan tâm."
    if ask_compare_price and book_titles:
        return "Mình chưa đủ dữ liệu để so sánh giá giữa các sản phẩm bạn nêu. Bạn thử ghi rõ tên từng sản phẩm trong dấu nháy nhé."
    if ask_next_book:
        return "Mình chưa có đủ ngữ cảnh để gợi ý sản phẩm tiếp theo. Bạn có thể nêu sản phẩm bạn vừa xem hoặc vừa mua."
    if ask_same_author:
        return "Mình chưa tìm thấy sản phẩm cùng tác giả theo yêu cầu. Bạn thử cho mình tên tác giả cụ thể nhé."
    if ask_price:
        bmin = entities.get("budget_min")
        bmax = entities.get("budget_max")
        if bmin is not None and bmax is not None:
            return f"Mình chưa tìm thấy sản phẩm trong khoảng {_fmt_price(float(bmin))} - {_fmt_price(float(bmax))}. Bạn thử nới rộng khoảng giá nhé."
        if bmin is not None:
            return f"Mình chưa tìm thấy sản phẩm có giá từ {_fmt_price(float(bmin))} trở lên trong dữ liệu hiện tại."
        if bmax is not None:
            return f"Mình chưa tìm thấy sản phẩm có giá dưới {_fmt_price(float(bmax))} trong dữ liệu hiện tại."
        return "Mình chưa tìm thấy thông tin giá theo yêu cầu của bạn."
    if ask_bestseller:
        return "Hiện chưa đủ dữ liệu để xếp hạng sản phẩm bán chạy. Bạn thử lại sau khi có thêm lượt mua/đánh giá nhé."
    if ask_new_books:
        return "Hiện chưa có dữ liệu sản phẩm mới trong kho. Bạn thử lại sau nhé."

    kw_str = ", ".join(keywords[:3]) if keywords else "từ khóa"
    return (
        f"Không tìm thấy kết quả cho '{kw_str}'. "
        "Thử tìm với từ khóa khác hoặc hỏi tôi về thể loại sản phẩm bạn quan tâm! 🔍"
    )


def _compose_fallback(entities: dict, data: dict, customer_id: int | None) -> str:
    sources = data.get("sources", [])
    if sources:
        return (
            f"Tôi tìm thấy thông tin có thể liên quan:\n\n"
            f"**{sources[0]['title']}**\n{sources[0]['content']}\n\n"
            "Bạn có muốn hỏi thêm điều gì không? 😊"
        )
    return (
        "Xin lỗi, tôi chưa hiểu rõ câu hỏi của bạn. 🤔\n\n"
        "Tôi có thể giúp bạn:\n"
        "• 💡 **Gợi ý sản phẩm** — 'Gợi ý sản phẩm cho tôi'\n"
        "• 🔍 **Tìm sản phẩm** — 'Tìm điện thoại dưới 5000000' hoặc 'So sánh giá sản phẩm A và B'\n"
        "• 📦 **Đơn hàng** — 'Đơn hàng của tôi'\n"
        "• 🔄 **Đổi trả** — 'Chính sách đổi trả'\n"
        "• 💳 **Thanh toán** — 'Phương thức thanh toán'"
    )
