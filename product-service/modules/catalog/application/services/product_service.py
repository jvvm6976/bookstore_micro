from ..commands.create_product import CreateProductCommand
from ..commands.create_variant import CreateVariantCommand
from ..commands.update_product import UpdateProductCommand
from ..queries.get_product import GetProductQuery
from ..queries.list_products import ListProductsQuery
from ..queries.filter_products import FilterProductsQuery


class ProductService:
    def __init__(self, repository):
        self.repository = repository

    def create_product(self, data):
        return CreateProductCommand(self.repository).execute(data)

    def update_product(self, product_id, data):
        return UpdateProductCommand(self.repository).execute(product_id, data)

    def create_variant(self, data):
        return CreateVariantCommand(self.repository).execute(data)

    def get_product(self, product_id):
        return GetProductQuery(self.repository).execute(product_id)

    def list_products(self):
        return ListProductsQuery(self.repository).execute()

    def filter_products(self, params):
        return FilterProductsQuery(self.repository).execute(params)
