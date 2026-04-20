from dataclasses import dataclass


@dataclass(frozen=True)
class SKU:
    value: str
