import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Shipment


class Command(BaseCommand):
    help = "Seed shipment fixtures (idempotent)."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "shipment_fixtures.json"
        with fixture_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        count = 0
        for item in payload.get("shipments", []):
            sid = int(item["id"])
            defaults = {
                "order_id": int(item["order_id"]),
                "status": item["status"],
                "shipping_address": item["shipping_address"],
                "tracking_number": item.get("tracking_number"),
                "shipping_method": item.get("shipping_method", "standard"),
                "estimated_delivery": item.get("estimated_delivery"),
            }
            Shipment.objects.update_or_create(id=sid, defaults=defaults)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded shipment fixtures: {count} records"))
