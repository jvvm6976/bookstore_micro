from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class Attributes:
    value: Dict[str, Any] = field(default_factory=dict)
