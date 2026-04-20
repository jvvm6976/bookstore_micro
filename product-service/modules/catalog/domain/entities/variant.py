from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass
class Variant:
    id: Optional[int]
    product_id: int
    sku: str
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    price_delta: Decimal = Decimal('0')
    stock: int = 0
