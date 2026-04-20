import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Order, OrderItem


class Command(BaseCommand):
    help = "Seed order and order-item fixtures (idempotent)."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "order_fixtures.json"
        with fixture_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        order_count = 0
        item_count = 0

        for item in payload.get("orders", []):
            oid = int(item["id"])
            defaults = {
                "customer_id": int(item["customer_id"]),
                "total_amount": item["total_amount"],
                "status": item["status"],
                "shipping_address": item.get("shipping_address", ""),
            }
            Order.objects.update_or_create(id=oid, defaults=defaults)
            order_count += 1

        for item in payload.get("order_items", []):
            iid = int(item["id"])
            defaults = {
                "order_id": int(item["order_id"]),
                "book_id": int(item["book_id"]),
                "quantity": int(item["quantity"]),
                "price": item["price"],
            }
            OrderItem.objects.update_or_create(id=iid, defaults=defaults)
            item_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded order fixtures: {order_count} orders, {item_count} items"
        ))
