from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from app.clients.catalog_client import catalog_client
from app.models import CustomerProductInteraction


CUSTOMER_PROFILES = [
    {
        "customer_id": 290,
        "name": "Ngoc Lan",
        "primary": [30, 92, 21],
        "secondary": [28, 23, 12, 17],
        "explore": [1, 94, 96],
    },
    {
        "customer_id": 291,
        "name": "Hoang Nam",
        "primary": [25, 26, 29],
        "secondary": [16, 17, 5, 92],
        "explore": [27, 21, 28],
    },
    {
        "customer_id": 292,
        "name": "Mai Linh",
        "primary": [12, 13, 30],
        "secondary": [10, 11, 23, 28],
        "explore": [1, 24, 92],
    },
    {
        "customer_id": 293,
        "name": "Gia Huy",
        "primary": [4, 16, 17],
        "secondary": [5, 6, 15, 29],
        "explore": [25, 27, 97],
    },
    {
        "customer_id": 300,
        "name": "Lan Anh",
        "primary": [8, 23, 30],
        "secondary": [19, 93, 24, 92],
        "explore": [7, 20, 28],
    },
    {
        "customer_id": 301,
        "name": "Tuan Minh",
        "primary": [6, 10, 30],
        "secondary": [15, 16, 17, 94],
        "explore": [11, 96, 97],
    },
    {
        "customer_id": 302,
        "name": "Kim Ngan",
        "primary": [21, 23, 28],
        "secondary": [22, 24, 30, 92],
        "explore": [12, 94, 96],
    },
    {
        "customer_id": 303,
        "name": "Hai Dang",
        "primary": [25, 29, 16],
        "secondary": [26, 17, 5, 4],
        "explore": [27, 92, 97],
    },
    {
        "customer_id": 304,
        "name": "Thao Nhi",
        "primary": [8, 19, 23],
        "secondary": [93, 20, 24, 21],
        "explore": [12, 30, 92],
    },
]


PRIMARY_EVENTS = [
    ("search", 4, None),
    ("view_detail", 6, None),
    ("wishlist", 3, None),
    ("add_to_cart", 3, None),
    ("purchase", 2, None),
    ("rate_product", 1, 5),
    ("click_recommendation", 2, None),
]
SECONDARY_EVENTS = [
    ("search", 3, None),
    ("view_detail", 4, None),
    ("wishlist", 2, None),
    ("add_to_cart", 1, None),
    ("click_recommendation", 1, None),
]
EXPLORE_EVENTS = [
    ("search", 2, None),
    ("view_detail", 2, None),
    ("wishlist", 1, None),
]


def _price_range(price: float) -> int:
    if price < 300_000:
        return 1
    if price < 2_000_000:
        return 2
    if price < 10_000_000:
        return 3
    return 4


class Command(BaseCommand):
    help = "Seed realistic, diverse personalization signals for named customers."

    def handle(self, *args, **options):
        product_ids = sorted({
            pid
            for profile in CUSTOMER_PROFILES
            for key in ("primary", "secondary", "explore")
            for pid in profile[key]
        })
        products = {}
        for product_id in product_ids:
            product = catalog_client.get_product_by_id(product_id)
            if product:
                products[product_id] = product

        now = timezone.now()
        touched = 0
        missing_products = []
        for customer_index, profile in enumerate(CUSTOMER_PROFILES):
            groups = [
                (profile["primary"], PRIMARY_EVENTS),
                (profile["secondary"], SECONDARY_EVENTS),
                (profile["explore"], EXPLORE_EVENTS),
            ]
            event_offset = 0
            for product_ids_in_group, event_templates in groups:
                for product_id in product_ids_in_group:
                    product = products.get(product_id)
                    if not product:
                        missing_products.append(product_id)
                        continue
                    category = product.get("category_name") or product.get("category") or ""
                    price = float(product.get("price") or 0)
                    for interaction_type, count, rating in event_templates:
                        obj, _ = CustomerProductInteraction.objects.get_or_create(
                            customer_id=profile["customer_id"],
                            product_id=product_id,
                            interaction_type=interaction_type,
                            defaults={
                                "count": count,
                                "rating": rating,
                                "category": category,
                                "price_range": _price_range(price),
                            },
                        )
                        target_count = max(int(obj.count or 0), count)
                        timestamp = now - timedelta(
                            days=customer_index * 2 + event_offset // 5,
                            hours=event_offset % 5,
                        )
                        CustomerProductInteraction.objects.filter(pk=obj.pk).update(
                            count=target_count,
                            rating=rating if rating is not None else obj.rating,
                            category=category,
                            price_range=_price_range(price),
                            timestamp=timestamp,
                        )
                        event_offset += 1
                        touched += 1

        rows = CustomerProductInteraction.objects.filter(
            customer_id__in=[profile["customer_id"] for profile in CUSTOMER_PROFILES]
        ).count()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded personalization signals: touched={touched}, customer_rows={rows}"
        ))
        if missing_products:
            self.stdout.write(self.style.WARNING(
                f"Missing product ids skipped: {sorted(set(missing_products))}"
            ))
