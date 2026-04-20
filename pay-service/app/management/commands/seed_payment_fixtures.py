import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Payment


class Command(BaseCommand):
    help = "Seed payment fixtures (idempotent)."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "payment_fixtures.json"
        with fixture_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        count = 0
        for item in payload.get("payments", []):
            pid = int(item["id"])
            defaults = {
                "order_id": int(item["order_id"]),
                "amount": item["amount"],
                "status": item["status"],
                "payment_method": item.get("payment_method", "credit_card"),
                "transaction_id": item.get("transaction_id"),
            }
            Payment.objects.update_or_create(id=pid, defaults=defaults)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded payment fixtures: {count} records"))
