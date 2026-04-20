from dataclasses import dataclass
from typing import Optional


@dataclass
class Brand:
    id: Optional[int]
    name: str
    slug: str
    logo_url: str = ''
