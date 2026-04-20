import os
import random

import requests
from django.core.management.base import BaseCommand

from ...models import Comment


ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8000")
PAID_STATUSES = {"paid", "shipped"}

REVIEW_TEMPLATES = [
    "San pham dung nhu mo ta, chat luong tot.",
    "Giao nhanh, dong goi ky. Minh rat hai long.",
    "Gia hop ly so voi chat luong.",
    "Noi dung tot, se ung ho lan sau.",
    "Mau ma dep, trai nghiem su dung on dinh.",
    "Hop voi nhu cau cua minh, rat dang tien.",
    "Diem cong la chat luong va do ben.",
    "So voi ky vong thi kha tot.",
]


class Command(BaseCommand):
    help = "Seed bulk reviews from paid orders (one review per customer-book-order)."

    def add_arguments(self, parser):
        parser.add_argument("--max-reviews", type=int, default=300)
        parser.add_argument("--create-ratio", type=float, default=0.7)

    def _fetch_all_orders(self):
        orders = []
        next_url = f"{ORDER_SERVICE_URL}/api/orders/"

        while next_url:
            resp = requests.get(next_url, timeout=15)
            if resp.status_code != 200:
                raise RuntimeError(f"Cannot fetch orders: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            if isinstance(data, list):
                orders.extend(data)
                break
            rows = data.get("results", [])
            orders.extend(rows)
            next_url = data.get("next")

        return orders

    def handle(self, *args, **options):
        max_reviews = max(1, int(options["max_reviews"]))
        create_ratio = min(1.0, max(0.0, float(options["create_ratio"])))

        random.seed(20260416)
        orders = self._fetch_all_orders()
        paid_orders = [o for o in orders if str(o.get("status", "")).lower() in PAID_STATUSES]

        created = 0
        skipped = 0
        candidates = []

        for order in paid_orders:
            oid = int(order.get("id"))
            customer_id = int(order.get("customer_id"))
            for item in order.get("items", []) or []:
                book_id = int(item.get("book_id"))
                candidates.append((customer_id, book_id, oid))

        random.shuffle(candidates)
        for customer_id, book_id, order_id in candidates:
            if created >= max_reviews:
                break
            if random.random() > create_ratio:
                skipped += 1
                continue

            if Comment.objects.filter(customer_id=customer_id, book_id=book_id, order_id=order_id).exists():
                skipped += 1
                continue

            rating = random.choices([3, 4, 5], weights=[0.2, 0.45, 0.35], k=1)[0]
            content = random.choice(REVIEW_TEMPLATES)
            helpful_count = random.randint(0, 12)

            Comment.objects.create(
                customer_id=customer_id,
                book_id=book_id,
                order_id=order_id,
                content=content,
                rating=rating,
                helpful_count=helpful_count,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seed reviews done: created={created}, skipped={skipped}, paid_orders={len(paid_orders)}, candidates={len(candidates)}"
        ))
