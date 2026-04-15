"""
OrderSupportService
────────────────────
Handles order_support intent: fetches order + shipment + payment data
and formats a structured response.
"""
from __future__ import annotations
import logging
from typing import Any

from ..clients.order_client import order_client
from ..clients.ship_client import ship_client
from ..clients.pay_client import pay_client

logger = logging.getLogger(__name__)

STATUS_VI = {
    "pending":    "⏳ Chờ xử lý",
    "paid":       "✅ Đã thanh toán",
    "shipped":    "🚚 Đang giao hàng",
    "delivered":  "📬 Đã giao",
    "canceled":   "❌ Đã hủy",
    "processing": "🔄 Đang xử lý",
    "success":    "✅ Thành công",
    "failed":     "❌ Thất bại",
    "refunded":   "💰 Đã hoàn tiền",
}


def _fmt_status(s: str) -> str:
    return STATUS_VI.get(s, s)


def get_order_info(customer_id: int, order_id: int | None = None) -> dict[str, Any]:
    """
    Returns structured order info for chatbot response.
    If order_id given → single order detail.
    Else → list of recent orders.
    """
    if order_id:
        order = order_client.get_order_by_id(order_id)
        if not order:
            return {
                "found": False,
                "message": f"Không tìm thấy đơn hàng #{order_id}. Vui lòng kiểm tra lại mã đơn.",
            }

        ship    = ship_client.get_shipping_status(order_id) or {}
        payment = pay_client.get_payment_status(order_id) or {}

        return {
            "found":    True,
            "order_id": order_id,
            "status":   _fmt_status(order.get("status", "")),
            "total":    float(order.get("total_amount", 0)),
            "items":    order.get("items", []),
            "address":  order.get("shipping_address", ""),
            "created":  str(order.get("created_at", ""))[:10],
            "shipping": {
                "status":   _fmt_status(ship.get("status", "")),
                "tracking": ship.get("tracking_number", "Chưa có"),
                "eta":      ship.get("estimated_delivery", ""),
            },
            "payment": {
                "status": _fmt_status(payment.get("status", "")),
                "method": payment.get("payment_method", ""),
            },
        }

    # List recent orders
    orders = order_client.get_orders_by_customer(customer_id)
    if not orders:
        return {
            "found":   False,
            "message": "Bạn chưa có đơn hàng nào. Hãy khám phá sách và đặt hàng ngay!",
        }

    summaries = []
    for o in orders[:5]:
        oid = o.get("id")
        summaries.append({
            "order_id": oid,
            "status":   _fmt_status(o.get("status", "")),
            "total":    float(o.get("total_amount", 0)),
            "items":    len(o.get("items", [])),
            "created":  str(o.get("created_at", ""))[:10],
        })

    return {
        "found":   True,
        "orders":  summaries,
        "count":   len(orders),
    }


order_support_service = type("OrderSupportService", (), {
    "get_order_info": staticmethod(get_order_info),
})()
