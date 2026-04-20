from ..models import Product, ProductVariant


class DjangoProductRepository:
    def list(self):
        return Product.objects.all()

    def get(self, product_id: int):
        return Product.objects.get(pk=product_id)

    def filter(self, params):
        return Product.objects.apply_filters(params)

    def create(self, data):
        return Product.objects.create(**data)

    def update(self, product_id, data):
        product = self.get(product_id)
        for key, value in data.items():
            if hasattr(product, key):
                setattr(product, key, value)
        product.save()
        return product

    def create_variant(self, data):
        return ProductVariant.objects.create(**data)
