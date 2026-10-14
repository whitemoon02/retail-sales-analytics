import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pipeline import clean  # noqa: E402


def test_clean_removes_invalid_lines_and_computes_revenue():
    items = pd.DataFrame({
        "line_id": [1, 2, 3, 3], "order_id": [1, 1, 2, 2], "product_id": [1, 2, 3, 3],
        "quantity": [2, -1, 1, 1], "unit_price": [10.0, 5.0, None, None], "discount": [0.1, 0, 0, 0],
    })
    orders = pd.DataFrame({"order_id": [1, 2], "order_date": ["2024-01-01", "2024-01-02"]})
    out = clean({"order_items": items, "orders": orders})
    assert list(out["order_items"].line_id) == [1]
    assert out["order_items"].revenue.iloc[0] == 18.0
    assert list(out["orders"].order_id) == [1]
