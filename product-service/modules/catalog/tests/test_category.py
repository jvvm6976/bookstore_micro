from django.test import TestCase

from ..infrastructure.models import Category


class CategoryTests(TestCase):
    def test_create_category(self):
        category = Category.objects.create(slug='electronics', name='Electronics')
        self.assertEqual(category.slug, 'electronics')
