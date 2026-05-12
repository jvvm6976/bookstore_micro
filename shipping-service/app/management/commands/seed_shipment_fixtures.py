import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Shipment, ShipmentTracking


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
                "receiver_name": item["receiver_name"],
                "phone": item["phone"],
                "full_address": item["full_address"],
                "current_status": item.get("current_status", "processing"),
            }
            shipment, created = Shipment.objects.update_or_create(id=sid, defaults=defaults)
            if created:
                ShipmentTracking.objects.create(
                    shipment=shipment,
                    status=shipment.current_status,
                    location="Warehouse",
                )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {count} shipments"))
