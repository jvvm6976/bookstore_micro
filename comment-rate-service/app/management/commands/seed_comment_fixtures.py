import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Review


class Command(BaseCommand):
    help = "Seed review fixtures (idempotent by user_id+product_id+order_id)."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "comment_fixtures.json"
        with fixture_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        count = 0
        for item in payload.get("reviews", []):
            lookup = {
                "user_id": int(item["user_id"]),
                "product_id": int(item["product_id"]),
                "order_id": int(item["order_id"]),
            }
            defaults = {
                "rating": int(item["rating"]),
                "comment": item.get("comment", ""),
                "status": item.get("status", "approved"),
            }
            Review.objects.update_or_create(**lookup, defaults=defaults)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {count} reviews"))
