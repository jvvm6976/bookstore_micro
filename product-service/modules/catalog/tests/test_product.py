from django.test import TestCase

from ..infrastructure.models import Brand, Category, Product, ProductType


class ProductTests(TestCase):
    def setUp(self):
        self.product_type = ProductType.objects.create(slug='laptop', name='Laptop', icon='💻')
        self.category = Category.objects.create(slug='electronics', name='Electronics')
        self.brand = Brand.objects.create(slug='apple', name='Apple')

    def test_create_product(self):
        product = Product.objects.create(
            slug='macbook-pro-14',
            name='MacBook Pro 14',
            product_type=self.product_type,
            category=self.category,
            brand=self.brand,
            price='49990000.00',
            stock=5,
        )
        self.assertEqual(product.name, 'MacBook Pro 14')
