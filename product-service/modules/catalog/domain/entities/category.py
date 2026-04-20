from dataclasses import dataclass
from typing import Optional


@dataclass
class Category:
    id: Optional[int]
    name: str
    slug: str
    parent_id: Optional[int] = None
    description: str = ''
    image_url: str = ''
