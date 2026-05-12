from django.core.management.base import BaseCommand
from app.models import Domain, Category


class Command(BaseCommand):
    help = 'Seed domains and categories'

    def handle(self, *args, **options):
        # Create domains
        domains_data = [
            {'name': 'Books', 'description': 'Books and literature'},
            {'name': 'Electronics', 'description': 'Electronic devices and gadgets'},
            {'name': 'Fashion', 'description': 'Clothing and fashion items'},
        ]

        domains = {}
        for domain_data in domains_data:
            domain, created = Domain.objects.get_or_create(
                name=domain_data['name'],
                defaults={'description': domain_data['description']}
            )
            domains[domain_data['name']] = domain
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created domain: {domain.name}'))

        # Create categories for each domain
        categories_data = {
            'Books': [
                {'name': 'Fiction', 'description': 'Fiction books'},
                {'name': 'Non-fiction', 'description': 'Non-fiction books'},
                {'name': 'Science', 'description': 'Science books'},
            ],
            'Electronics': [
                {'name': 'Phones', 'description': 'Mobile phones'},
                {'name': 'Laptops', 'description': 'Laptop computers'},
                {'name': 'Accessories', 'description': 'Electronic accessories'},
            ],
            'Fashion': [
                {'name': 'Men', 'description': 'Men clothing'},
                {'name': 'Women', 'description': 'Women clothing'},
                {'name': 'Shoes', 'description': 'Footwear'},
            ],
        }

        for domain_name, categories in categories_data.items():
            domain = domains[domain_name]
            for category_data in categories:
                category, created = Category.objects.get_or_create(
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

        self.stdout.write(self.style.SUCCESS('Successfully seeded domains and categories'))
