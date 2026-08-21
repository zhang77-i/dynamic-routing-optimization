from pathlib import Path

from src.data.solomon_loader import load_solomon_instance


def test_solomon_loader():
    path = Path("data/solomon/C101.txt")

    if path.exists():
        customers = load_solomon_instance(path)
        assert len(customers) > 0
        assert customers[0].customer_id >= 0
