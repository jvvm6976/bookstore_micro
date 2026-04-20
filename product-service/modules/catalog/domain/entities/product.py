from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class Product:
    id: Optional[int]
    name: str
    price: Decimal
    stock: int = 0
    description: str = ''
    category_slug: str = ''
    brand_slug: str = ''
    product_type_slug: str = ''
    sku: str = ''
    attributes: Dict[str, Any] = field(default_factory=dict)
    images: List[str] = field(default_factory=list)
    is_active: bool = True

    def is_in_stock(self):
        return self.stock > 0

    def reduce_stock(self, qty):
        if qty > self.stock:
            return False
        self.stock -= qty
        return True
