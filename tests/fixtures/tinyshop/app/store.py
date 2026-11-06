import json
import os

from .models import Order, Product

CATALOG = [
    Product("tea", "Green tea", 450),
    Product("mug", "Stoneware mug", 1200),
    Product("kettle", "Gooseneck kettle", 3900),
]


class Store:
    """Keeps orders in a JSON file so they survive restarts."""

    def __init__(self, path=None):
        self.path = path or os.environ.get("SHOP_DATA", "orders.json")
        self.orders = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path) as fh:
            return [Order(**o) for o in json.load(fh)]

    def products(self):
        return CATALOG

    def place_order(self, skus):
        prices = {p.sku: p.price_cents for p in CATALOG}
        unknown = [s for s in skus if s not in prices]
        if unknown:
            raise KeyError("unknown sku: " + ", ".join(unknown))
        order = Order(id=len(self.orders) + 1, items=list(skus),
                      total_cents=sum(prices[s] for s in skus))
        self.orders.append(order)
        self._save()
        return order

    def _save(self):
        with open(self.path, "w") as fh:
            json.dump([o.__dict__ for o in self.orders], fh)
