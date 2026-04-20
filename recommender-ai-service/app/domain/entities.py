from dataclasses import dataclass, field
from typing import Any


@dataclass
class InteractionEvent:
    customer_id: int
    product_id: int
    interaction_type: str
    category: str = ""
    brand: str = ""
    product_type: str = ""
    timestamp: str = ""


@dataclass
class RecommendationCandidate:
    product_id: int
    title: str
    author: str = ""
    category: str = ""
    price: float = 0.0
    score: float = 0.0
    reason: str = ""
    avg_rating: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
