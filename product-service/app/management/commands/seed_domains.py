from django.core.management.base import BaseCommand
from app.models import Domain, Category


class Command(BaseCommand):
    help = 'Seed domains and categories'

    def handle(self, *args, **options):
        domains_data = [
            {'name': 'Books', 'description': 'Books and literature for work, study, and leisure.'},
            {'name': 'Electronics', 'description': 'Phones, laptops, and everyday technology.'},
            {'name': 'Fashion', 'description': 'Clothing, footwear, and personal style items.'},
            {'name': 'Home & Kitchen', 'description': 'Practical products for cooking, cleaning, and home living.'},
            {'name': 'Beauty & Personal Care', 'description': 'Skincare, haircare, fragrance, and daily care products.'},
            {'name': 'Sports & Outdoors', 'description': 'Fitness, camping, cycling, and outdoor activity gear.'},
            {'name': 'Toys & Games', 'description': 'Board games, building sets, and learning toys.'},
            {'name': 'Grocery', 'description': 'Coffee, snacks, pantry staples, and daily grocery items.'},
            {'name': 'Automotive', 'description': 'Car care, motorcycle gear, and vehicle accessories.'},
            {'name': 'Office & Stationery', 'description': 'Notebooks, writing tools, and desk accessories.'},
        ]

        domains = {}
        for domain_data in domains_data:
            domain, created = Domain.objects.update_or_create(
                name=domain_data['name'],
                defaults={'description': domain_data['description']}
            )
            domains[domain_data['name']] = domain
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created domain: {domain.name}'))

        categories_data = {
            'Books': [
                {'name': 'Fiction', 'description': 'Fiction books'},
                {'name': 'Non-Fiction', 'description': 'Non-fiction books'},
                {'name': 'Science', 'description': 'Science books'},
            ],
            'Electronics': [
                {'name': 'Phones', 'description': 'Smartphones'},
                {'name': 'Laptops', 'description': 'Laptop computers'},
                {'name': 'Accessories', 'description': 'Electronic accessories'},
            ],
            'Fashion': [
                {'name': 'Mens', 'description': 'Mens clothing'},
                {'name': 'Womens', 'description': 'Womens clothing'},
                {'name': 'Shoes', 'description': 'Footwear'},
            ],
            'Home & Kitchen': [
                {'name': 'Cookware', 'description': 'Pots, pans, and cooking tools'},
                {'name': 'Appliances', 'description': 'Kitchen and household appliances'},
                {'name': 'Decor', 'description': 'Home decor and organization'},
            ],
            'Beauty & Personal Care': [
                {'name': 'Skincare', 'description': 'Face and body skincare'},
                {'name': 'Haircare', 'description': 'Hair washing, care, and styling'},
                {'name': 'Fragrance', 'description': 'Perfume and personal fragrance'},
            ],
            'Sports & Outdoors': [
                {'name': 'Fitness', 'description': 'Training and exercise equipment'},
                {'name': 'Camping', 'description': 'Camping and hiking gear'},
                {'name': 'Cycling', 'description': 'Bikes, helmets, and cycling accessories'},
            ],
            'Toys & Games': [
                {'name': 'Board Games', 'description': 'Strategy and family board games'},
                {'name': 'Building Sets', 'description': 'Construction and creative building toys'},
                {'name': 'Learning Toys', 'description': 'Educational toys for children'},
            ],
            'Grocery': [
                {'name': 'Coffee & Tea', 'description': 'Coffee beans, tea, and brewing supplies'},
                {'name': 'Snacks', 'description': 'Packaged snacks and treats'},
                {'name': 'Pantry', 'description': 'Shelf-stable pantry staples'},
            ],
            'Automotive': [
                {'name': 'Car Care', 'description': 'Cleaning and maintenance for cars'},
                {'name': 'Motorcycle Gear', 'description': 'Riding equipment and protection'},
                {'name': 'Vehicle Accessories', 'description': 'Accessories for cars and motorcycles'},
            ],
            'Office & Stationery': [
                {'name': 'Notebooks', 'description': 'Notebooks, journals, and planners'},
                {'name': 'Writing', 'description': 'Pens, pencils, and writing supplies'},
                {'name': 'Desk Accessories', 'description': 'Desk organization and productivity tools'},
            ],
        }

        for domain_name, categories in categories_data.items():
            domain = domains[domain_name]
            for category_data in categories:
                category, created = Category.objects.update_or_create(
                    name=category_data['name'],
                    domain=domain,
                    defaults={'description': category_data['description']}
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created category: {category.name} in domain {domain.name}'
                        )
                    )

        legacy_category_names = {
            'Books': ['Non-fiction'],
            'Fashion': ['Men', 'Women'],
        }
        for domain_name, names in legacy_category_names.items():
            deleted_count, _ = Category.objects.filter(
                domain=domains[domain_name],
                name__in=names,
                products__isnull=True,
            ).delete()
            if deleted_count:
                self.stdout.write(
                    self.style.WARNING(
                        f'Removed {deleted_count} empty legacy categories in domain {domain_name}'
                    )
                )

        self.stdout.write(self.style.SUCCESS('Successfully seeded domains and categories'))
