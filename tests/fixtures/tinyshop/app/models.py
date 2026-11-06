from dataclasses import dataclass, field
from typing import List


@dataclass
class Product:
    sku: str
    name: str
    price_cents: int


@dataclass
class Order:
    id: int
    items: List[str] = field(default_factory=list)
    total_cents: int = 0
