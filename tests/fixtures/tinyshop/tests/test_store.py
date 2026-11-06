import os
import tempfile
import unittest

from app.store import Store


class StoreTest(unittest.TestCase):
    def test_order_total(self):
        path = os.path.join(tempfile.mkdtemp(), "orders.json")
        order = Store(path).place_order(["tea", "mug"])
        self.assertEqual(order.total_cents, 1650)
