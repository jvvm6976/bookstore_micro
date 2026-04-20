from django.core.management.base import BaseCommand

from ...infrastructure.models import Brand, Category, Product, ProductType
from ...seeds import BRANDS, CATEGORIES, PRODUCTS, PRODUCT_TYPES


class Command(BaseCommand):
    help = 'Seed the product catalog with sample products.'

    def handle(self, *args, **options):
        type_map = {}
        category_map = {}
        brand_map = {}

        for item in PRODUCT_TYPES:
            obj, _ = ProductType.objects.update_or_create(
                slug=item['slug'],
                defaults={'name': item['name'], 'icon': item['icon']},
            )
            type_map[item['slug']] = obj

        for item in CATEGORIES:
            obj, _ = Category.objects.update_or_create(
                slug=item['slug'],
                defaults={'name': item['name']},
            )
            category_map[item['slug']] = obj

        for item in BRANDS:
            obj, _ = Brand.objects.update_or_create(
                slug=item['slug'],
                defaults={'name': item['name'], 'country': item['country']},
            )
            brand_map[item['slug']] = obj

        created = 0
        for item in PRODUCTS:
            Product.objects.update_or_create(
                slug=item['slug'],
                defaults={
                    'name': item['name'],
                    'author': item.get('author') or '',
                    'product_type': type_map[item['type']],
                    'category': category_map[item['category']],
                    'brand': brand_map[item['brand']],
                    'price': item['price'],
                    'stock': item['stock'],
                    'description': item['description'],
                    'cover_image_url': item['cover_image_url'],
                    'attributes': item.get('attributes', {}),
                    'is_active': True,
                },
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created} products, {len(type_map)} product types, {len(category_map)} categories and {len(brand_map)} brands.'
        ))
