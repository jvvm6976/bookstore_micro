import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...models import Comment


class Command(BaseCommand):
    help = "Seed comment fixtures (idempotent by customer_id+book_id+order_id)."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "comment_fixtures.json"
        with fixture_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        count = 0
        for item in payload.get("comments", []):
            lookup = {
                "customer_id": int(item["customer_id"]),
                "book_id": int(item["book_id"]),
                "order_id": int(item.get("order_id", 0)),
            }
            defaults = {
                "content": item["content"],
                "rating": int(item.get("rating", 5)),
                "helpful_count": int(item.get("helpful_count", 0)),
            }
            Comment.objects.update_or_create(**lookup, defaults=defaults)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded comment fixtures: {count} records"))
