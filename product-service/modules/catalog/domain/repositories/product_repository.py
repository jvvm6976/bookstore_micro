from typing import Protocol


class ProductRepository(Protocol):
    def list(self):
        ...

    def get(self, product_id: int):
        ...

    def save(self, product):
        ...
