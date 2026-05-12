from django.core.management.base import BaseCommand
from app.models import Domain, Category, Product, Book, Electronics, Fashion

class Command(BaseCommand):
    help = 'Seed product database with initial data'

    def handle(self, *args, **options):
        # Create Domains
        books_domain, _ = Domain.objects.get_or_create(
            name='Books',
            defaults={'description': 'Books and literature'}
        )
        electronics_domain, _ = Domain.objects.get_or_create(
            name='Electronics',
            defaults={'description': 'Electronic devices and gadgets'}
        )
        fashion_domain, _ = Domain.objects.get_or_create(
            name='Fashion',
            defaults={'description': 'Clothing and fashion items'}
        )

        # Create Categories for Books
        fiction_cat, _ = Category.objects.get_or_create(
            name='Fiction',
            domain=books_domain,
            defaults={'description': 'Fiction books'}
        )
        non_fiction_cat, _ = Category.objects.get_or_create(
            name='Non-Fiction',
            domain=books_domain,
            defaults={'description': 'Non-fiction books'}
        )
        science_cat, _ = Category.objects.get_or_create(
            name='Science',
            domain=books_domain,
            defaults={'description': 'Science books'}
        )

        # Create Categories for Electronics
        phones_cat, _ = Category.objects.get_or_create(
            name='Phones',
            domain=electronics_domain,
            defaults={'description': 'Mobile phones'}
        )
        laptops_cat, _ = Category.objects.get_or_create(
            name='Laptops',
            domain=electronics_domain,
            defaults={'description': 'Laptop computers'}
        )
        accessories_cat, _ = Category.objects.get_or_create(
            name='Accessories',
            domain=electronics_domain,
            defaults={'description': 'Electronic accessories'}
        )

        # Create Categories for Fashion
        mens_cat, _ = Category.objects.get_or_create(
            name='Mens',
            domain=fashion_domain,
            defaults={'description': 'Mens clothing'}
        )
        womens_cat, _ = Category.objects.get_or_create(
            name='Womens',
            domain=fashion_domain,
            defaults={'description': 'Womens clothing'}
        )
        shoes_cat, _ = Category.objects.get_or_create(
            name='Shoes',
            domain=fashion_domain,
            defaults={'description': 'Shoes and footwear'}
        )

        # Create Books
        book1, _ = Product.objects.get_or_create(
            sku='BOOK001',
            defaults={
                'name': 'The Great Gatsby',
                'description': 'A classic American novel',
                'price': '15.99',
                'stock': 100,
                'status': 'active',
                'category': fiction_cat
            }
        )
        if _:
            Book.objects.create(
                product=book1,
                author='F. Scott Fitzgerald',
                publisher='Scribner',
                isbn='978-0743273565'
            )

        book2, _ = Product.objects.get_or_create(
            sku='BOOK002',
            defaults={
                'name': 'To Kill a Mockingbird',
                'description': 'A gripping tale of racial injustice',
                'price': '18.99',
                'stock': 80,
                'status': 'active',
                'category': fiction_cat
            }
        )
        if _:
            Book.objects.create(
                product=book2,
                author='Harper Lee',
                publisher='J.B. Lippincott',
                isbn='978-0061120084'
            )

        book3, _ = Product.objects.get_or_create(
            sku='BOOK003',
            defaults={
                'name': 'A Brief History of Time',
                'description': 'Understanding the universe',
                'price': '22.99',
                'stock': 60,
                'status': 'active',
                'category': science_cat
            }
        )
        if _:
            Book.objects.create(
                product=book3,
                author='Stephen Hawking',
                publisher='Bantam',
                isbn='978-0553380163'
            )

        # Create Electronics
        phone1, _ = Product.objects.get_or_create(
            sku='PHONE001',
            defaults={
                'name': 'iPhone 15 Pro',
                'description': 'Latest Apple smartphone',
                'price': '999.99',
                'stock': 50,
                'status': 'active',
                'category': phones_cat
            }
        )
        if _:
            Electronics.objects.create(
                product=phone1,
                brand='Apple',
                warranty_months=12
            )

        phone2, _ = Product.objects.get_or_create(
            sku='PHONE002',
            defaults={
                'name': 'Samsung Galaxy S24',
                'description': 'Premium Android phone',
                'price': '899.99',
                'stock': 45,
                'status': 'active',
                'category': phones_cat
            }
        )
        if _:
            Electronics.objects.create(
                product=phone2,
                brand='Samsung',
                warranty_months=12
            )

        laptop1, _ = Product.objects.get_or_create(
            sku='LAPTOP001',
            defaults={
                'name': 'MacBook Pro 16',
                'description': 'Powerful laptop for professionals',
                'price': '2499.99',
                'stock': 20,
                'status': 'active',
                'category': laptops_cat
            }
        )
        if _:
            Electronics.objects.create(
                product=laptop1,
                brand='Apple',
                warranty_months=12
            )

        # Create Fashion
        shirt1, _ = Product.objects.get_or_create(
            sku='SHIRT001',
            defaults={
                'name': 'Cotton T-Shirt',
                'description': 'Comfortable cotton shirt',
                'price': '29.99',
                'stock': 200,
                'status': 'active',
                'category': mens_cat
            }
        )
        if _:
            Fashion.objects.create(
                product=shirt1,
                size='M',
                color='Blue'
            )

        dress1, _ = Product.objects.get_or_create(
            sku='DRESS001',
            defaults={
                'name': 'Summer Dress',
                'description': 'Light and breezy summer dress',
                'price': '49.99',
                'stock': 150,
                'status': 'active',
                'category': womens_cat
            }
        )
        if _:
            Fashion.objects.create(
                product=dress1,
                size='S',
                color='Red'
            )

        shoes1, _ = Product.objects.get_or_create(
            sku='SHOES001',
            defaults={
                'name': 'Running Shoes',
                'description': 'Professional running shoes',
                'price': '89.99',
                'stock': 100,
                'status': 'active',
                'category': shoes_cat
            }
        )
        if _:
            Fashion.objects.create(
                product=shoes1,
                size='10',
                color='Black'
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded product database'))
