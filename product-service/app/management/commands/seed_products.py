import os

from django.core.management.base import BaseCommand
from django.db.models import Q

from app.models import Book, Category, Domain, Electronics, Fashion, Product


DOMAINS = [
    ('Books', 'Books and literature for work, study, and leisure.'),
    ('Electronics', 'Phones, laptops, and everyday technology.'),
    ('Fashion', 'Clothing, footwear, and personal style items.'),
    ('Home & Kitchen', 'Practical products for cooking, cleaning, and home living.'),
    ('Beauty & Personal Care', 'Skincare, haircare, fragrance, and daily care products.'),
    ('Sports & Outdoors', 'Fitness, camping, cycling, and outdoor activity gear.'),
    ('Toys & Games', 'Board games, building sets, and learning toys.'),
    ('Grocery', 'Coffee, snacks, pantry staples, and daily grocery items.'),
    ('Automotive', 'Car care, motorcycle gear, and vehicle accessories.'),
    ('Office & Stationery', 'Notebooks, writing tools, and desk accessories.'),
]

CATEGORIES = {
    'Books': [
        ('Fiction', 'Fiction books'),
        ('Non-Fiction', 'Non-fiction books'),
        ('Science', 'Science books'),
    ],
    'Electronics': [
        ('Phones', 'Smartphones'),
        ('Laptops', 'Laptop computers'),
        ('Accessories', 'Electronic accessories'),
    ],
    'Fashion': [
        ('Mens', 'Mens clothing'),
        ('Womens', 'Womens clothing'),
        ('Shoes', 'Shoes and footwear'),
    ],
    'Home & Kitchen': [
        ('Cookware', 'Pots, pans, and cooking tools'),
        ('Appliances', 'Kitchen and household appliances'),
        ('Decor', 'Home decor and organization'),
    ],
    'Beauty & Personal Care': [
        ('Skincare', 'Face and body skincare'),
        ('Haircare', 'Hair washing, care, and styling'),
        ('Fragrance', 'Perfume and personal fragrance'),
    ],
    'Sports & Outdoors': [
        ('Fitness', 'Training and exercise equipment'),
        ('Camping', 'Camping and hiking gear'),
        ('Cycling', 'Bikes, helmets, and cycling accessories'),
    ],
    'Toys & Games': [
        ('Board Games', 'Strategy and family board games'),
        ('Building Sets', 'Construction and creative building toys'),
        ('Learning Toys', 'Educational toys for children'),
    ],
    'Grocery': [
        ('Coffee & Tea', 'Coffee beans, tea, and brewing supplies'),
        ('Snacks', 'Packaged snacks and treats'),
        ('Pantry', 'Shelf-stable pantry staples'),
    ],
    'Automotive': [
        ('Car Care', 'Cleaning and maintenance for cars'),
        ('Motorcycle Gear', 'Riding equipment and protection'),
        ('Vehicle Accessories', 'Accessories for cars and motorcycles'),
    ],
    'Office & Stationery': [
        ('Notebooks', 'Notebooks, journals, and planners'),
        ('Writing', 'Pens, pencils, and writing supplies'),
        ('Desk Accessories', 'Desk organization and productivity tools'),
    ],
}

PRODUCTS = [
    {
        'sku': 'BOOK001',
        'name': 'The Great Gatsby',
        'description': 'F. Scott Fitzgerald classic American novel in paperback.',
        'price': '189000.00',
        'stock': 100,
        'domain': 'Books',
        'category': 'Fiction',
        'image': 1,
        'book': {'author': 'F. Scott Fitzgerald', 'publisher': 'Scribner', 'isbn': '978-0743273565'},
    },
    {
        'sku': 'BOOK002',
        'name': 'To Kill a Mockingbird',
        'description': 'Harper Lee novel about justice, family, and social conscience.',
        'price': '159000.00',
        'stock': 80,
        'domain': 'Books',
        'category': 'Fiction',
        'image': 2,
        'book': {'author': 'Harper Lee', 'publisher': 'J.B. Lippincott', 'isbn': '978-0061120084'},
    },
    {
        'sku': 'BOOK003',
        'name': 'A Brief History of Time',
        'description': 'Stephen Hawking introduction to cosmology and the universe.',
        'price': '145000.00',
        'stock': 60,
        'domain': 'Books',
        'category': 'Science',
        'image': 3,
        'book': {'author': 'Stephen Hawking', 'publisher': 'Bantam', 'isbn': '978-0553380163'},
    },
    {
        'sku': 'BOOK004',
        'name': 'Clean Code',
        'description': 'Practical software craftsmanship guide for maintainable code.',
        'price': '399000.00',
        'stock': 45,
        'domain': 'Books',
        'category': 'Science',
        'image': 4,
        'book': {'author': 'Robert C. Martin', 'publisher': 'Prentice Hall', 'isbn': '978-0132350884'},
    },
    {
        'sku': 'BOOK005',
        'name': 'Design Patterns',
        'description': 'Reusable object-oriented software design pattern reference.',
        'price': '520000.00',
        'stock': 30,
        'domain': 'Books',
        'category': 'Science',
        'image': 5,
        'book': {'author': 'Erich Gamma', 'publisher': 'Addison-Wesley', 'isbn': '978-0201633610'},
    },
    {
        'sku': 'BOOK006',
        'name': 'Atomic Habits',
        'description': 'Clear methods for building better habits and systems.',
        'price': '185000.00',
        'stock': 120,
        'domain': 'Books',
        'category': 'Non-Fiction',
        'image': 6,
        'book': {'author': 'James Clear', 'publisher': 'Avery', 'isbn': '978-0735211292'},
    },
    {
        'sku': 'BOOK007',
        'name': 'Sapiens',
        'description': 'A concise history of humankind and human society.',
        'price': '249000.00',
        'stock': 75,
        'domain': 'Books',
        'category': 'Non-Fiction',
        'image': 7,
        'book': {'author': 'Yuval Noah Harari', 'publisher': 'Harper', 'isbn': '978-0062316097'},
    },
    {
        'sku': 'BOOK008',
        'name': 'The Lean Startup',
        'description': 'Entrepreneurship book about validated learning and iteration.',
        'price': '175000.00',
        'stock': 90,
        'domain': 'Books',
        'category': 'Non-Fiction',
        'image': 8,
        'book': {'author': 'Eric Ries', 'publisher': 'Crown Business', 'isbn': '978-0307887894'},
    },
    {
        'sku': 'PHONE001',
        'name': 'iPhone 15 Pro',
        'description': 'Apple smartphone with titanium body and advanced camera system.',
        'price': '29990000.00',
        'stock': 50,
        'domain': 'Electronics',
        'category': 'Phones',
        'image': 9,
        'electronics': {'brand': 'Apple', 'warranty_months': 12},
    },
    {
        'sku': 'PHONE002',
        'name': 'Samsung Galaxy S24',
        'description': 'Premium smartphone with high-brightness display and AI features.',
        'price': '18990000.00',
        'stock': 45,
        'domain': 'Electronics',
        'category': 'Phones',
        'image': 10,
        'electronics': {'brand': 'Samsung', 'warranty_months': 12},
    },
    {
        'sku': 'LAPTOP001',
        'name': 'MacBook Pro 16',
        'description': 'High-performance Apple laptop for professional workloads.',
        'price': '64990000.00',
        'stock': 20,
        'domain': 'Electronics',
        'category': 'Laptops',
        'image': 11,
        'electronics': {'brand': 'Apple', 'warranty_months': 12},
    },
    {
        'sku': 'LAPTOP002',
        'name': 'Dell XPS 13',
        'description': 'Compact ultrabook with premium display and portable build.',
        'price': '32990000.00',
        'stock': 35,
        'domain': 'Electronics',
        'category': 'Laptops',
        'image': 12,
        'electronics': {'brand': 'Dell', 'warranty_months': 12},
    },
    {
        'sku': 'ACC001',
        'name': 'Sony WH-1000XM5 Headphones',
        'description': 'Wireless noise-canceling headphones for travel and work.',
        'price': '7990000.00',
        'stock': 65,
        'domain': 'Electronics',
        'category': 'Accessories',
        'image': 13,
        'electronics': {'brand': 'Sony', 'warranty_months': 12},
    },
    {
        'sku': 'ACC002',
        'name': 'Anker USB-C Hub',
        'description': 'Multi-port USB-C hub for laptops and tablets.',
        'price': '990000.00',
        'stock': 110,
        'domain': 'Electronics',
        'category': 'Accessories',
        'image': 14,
        'electronics': {'brand': 'Anker', 'warranty_months': 18},
    },
    {
        'sku': 'SHIRT001',
        'name': 'Cotton T-Shirt',
        'description': 'Soft cotton crew-neck t-shirt for everyday wear.',
        'price': '199000.00',
        'stock': 200,
        'domain': 'Fashion',
        'category': 'Mens',
        'image': 15,
        'fashion': {'size': 'M', 'color': 'Blue'},
    },
    {
        'sku': 'SHIRT002',
        'name': 'Oxford Button-Down Shirt',
        'description': 'Classic long-sleeve oxford shirt for smart casual outfits.',
        'price': '499000.00',
        'stock': 140,
        'domain': 'Fashion',
        'category': 'Mens',
        'image': 16,
        'fashion': {'size': 'L', 'color': 'White'},
    },
    {
        'sku': 'DRESS001',
        'name': 'Summer Dress',
        'description': 'Lightweight dress for warm weather and casual events.',
        'price': '599000.00',
        'stock': 150,
        'domain': 'Fashion',
        'category': 'Womens',
        'image': 17,
        'fashion': {'size': 'S', 'color': 'Red'},
    },
    {
        'sku': 'PANTS001',
        'name': 'Slim Fit Jeans',
        'description': 'Stretch denim jeans with a modern slim fit.',
        'price': '699000.00',
        'stock': 130,
        'domain': 'Fashion',
        'category': 'Womens',
        'image': 18,
        'fashion': {'size': 'M', 'color': 'Indigo'},
    },
    {
        'sku': 'SHOES001',
        'name': 'Running Shoes',
        'description': 'Lightweight running shoes with cushioned soles.',
        'price': '1890000.00',
        'stock': 100,
        'domain': 'Fashion',
        'category': 'Shoes',
        'image': 19,
        'fashion': {'size': '10', 'color': 'Black'},
    },
    {
        'sku': 'SHOES002',
        'name': 'Leather Chelsea Boots',
        'description': 'Durable leather ankle boots with elastic side panels.',
        'price': '2290000.00',
        'stock': 70,
        'domain': 'Fashion',
        'category': 'Shoes',
        'image': 20,
        'fashion': {'size': '9', 'color': 'Brown'},
    },
    {
        'sku': 'HOME001',
        'name': 'Stainless Steel Cookware Set',
        'description': 'Ten-piece cookware set for everyday home cooking.',
        'price': '1690000.00',
        'stock': 55,
        'domain': 'Home & Kitchen',
        'category': 'Cookware',
        'image': 21,
    },
    {
        'sku': 'HOME002',
        'name': 'Breville Barista Express Espresso Machine',
        'description': 'Countertop espresso machine with integrated grinder.',
        'price': '17990000.00',
        'stock': 18,
        'domain': 'Home & Kitchen',
        'category': 'Appliances',
        'image': 22,
    },
    {
        'sku': 'BEAUTY001',
        'name': 'CeraVe Hydrating Facial Cleanser',
        'description': 'Gentle daily cleanser for normal to dry skin.',
        'price': '285000.00',
        'stock': 160,
        'domain': 'Beauty & Personal Care',
        'category': 'Skincare',
        'image': 23,
    },
    {
        'sku': 'BEAUTY002',
        'name': 'Bleu de Chanel Eau de Parfum',
        'description': 'Woody aromatic fragrance in a spray bottle.',
        'price': '3890000.00',
        'stock': 42,
        'domain': 'Beauty & Personal Care',
        'category': 'Fragrance',
        'image': 24,
    },
    {
        'sku': 'SPORT001',
        'name': 'Bowflex SelectTech Adjustable Dumbbells',
        'description': 'Adjustable dumbbell pair for strength training at home.',
        'price': '12990000.00',
        'stock': 25,
        'domain': 'Sports & Outdoors',
        'category': 'Fitness',
        'image': 25,
    },
    {
        'sku': 'SPORT002',
        'name': 'Coleman Sundome Camping Tent',
        'description': 'Four-person dome tent for weekend camping trips.',
        'price': '2190000.00',
        'stock': 38,
        'domain': 'Sports & Outdoors',
        'category': 'Camping',
        'image': 26,
    },
    {
        'sku': 'TOY001',
        'name': 'Catan Board Game',
        'description': 'Strategy board game for families and game nights.',
        'price': '990000.00',
        'stock': 85,
        'domain': 'Toys & Games',
        'category': 'Board Games',
        'image': 27,
    },
    {
        'sku': 'GROCERY001',
        'name': 'Trung Nguyen Premium Coffee Beans',
        'description': 'Vietnamese whole-bean coffee for espresso and phin brewing.',
        'price': '145000.00',
        'stock': 180,
        'domain': 'Grocery',
        'category': 'Coffee & Tea',
        'image': 28,
    },
    {
        'sku': 'AUTO001',
        'name': "Meguiar's Car Wash Kit",
        'description': 'Car shampoo, microfiber towel, and detailing accessories.',
        'price': '890000.00',
        'stock': 95,
        'domain': 'Automotive',
        'category': 'Car Care',
        'image': 29,
    },
    {
        'sku': 'OFFICE001',
        'name': 'Moleskine Classic Notebook Set',
        'description': 'Hardcover ruled notebooks for office notes and planning.',
        'price': '690000.00',
        'stock': 125,
        'domain': 'Office & Stationery',
        'category': 'Notebooks',
        'image': 30,
    },
]

STALE_PRODUCT_SKU_PREFIXES = ('CUI-', 'DEEP-', 'UI-')
STALE_DOMAIN_PREFIXES = (
    'Codex UI ',
    'Deep ',
    'UI Shop ',
    'UI Ops ',
    'UI Manager ',
)



class Command(BaseCommand):
    help = 'Seed product database with 10 domains and realistic product data'

    def handle(self, *args, **options):
        image_base_url = os.environ.get(
            'PRODUCT_IMAGE_BASE_URL',
            'http://localhost:8002/static/images/products',
        ).rstrip('/')

        domains = {}
        for name, description in DOMAINS:
            domain, _ = Domain.objects.update_or_create(
                name=name,
                defaults={'description': description},
            )
            domains[name] = domain

        categories = {}
        for domain_name, category_rows in CATEGORIES.items():
            for category_name, description in category_rows:
                category, _ = Category.objects.update_or_create(
                    name=category_name,
                    domain=domains[domain_name],
                    defaults={'description': description},
                )
                categories[(domain_name, category_name)] = category

        created_count = 0
        updated_count = 0
        for item in PRODUCTS:
            product, created = Product.objects.update_or_create(
                sku=item['sku'],
                defaults={
                    'name': item['name'],
                    'description': item['description'],
                    'price': item['price'],
                    'stock': item['stock'],
                    'status': 'active',
                    'category': categories[(item['domain'], item['category'])],
                    'image_url': f"{image_base_url}/product_{item['image']}.jpg",
                },
            )

            if 'book' in item:
                Book.objects.update_or_create(product=product, defaults=item['book'])
            if 'electronics' in item:
                Electronics.objects.update_or_create(product=product, defaults=item['electronics'])
            if 'fashion' in item:
                Fashion.objects.update_or_create(product=product, defaults=item['fashion'])

            if created:
                created_count += 1
            else:
                updated_count += 1

        stale_filter = Q()
        for prefix in STALE_PRODUCT_SKU_PREFIXES:
            stale_filter |= Q(sku__startswith=prefix)
        stale_products_deleted = Product.objects.filter(stale_filter).delete()[0] if stale_filter else 0

        stale_domains_deleted = 0
        for prefix in STALE_DOMAIN_PREFIXES:
            stale_domains_deleted += Domain.objects.filter(name__startswith=prefix).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded {len(domains)} domains, {len(categories)} categories, '
                f'{created_count} new products, {updated_count} updated products, '
                f'{stale_products_deleted} stale test products removed, '
                f'and {stale_domains_deleted} stale test domains/categories removed.'
            )
        )
