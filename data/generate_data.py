"""Génère un jeu de données retail synthétique et réaliste (clients, produits, magasins, commandes).

Usage : python data/generate_data.py --orders 50000
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
OUT = Path(__file__).parent / "raw"

REGIONS = {
    "Île-de-France": ["Paris", "Créteil", "Versailles", "Nanterre"],
    "Auvergne-Rhône-Alpes": ["Lyon", "Grenoble", "Clermont-Ferrand"],
    "Provence-Alpes-Côte d'Azur": ["Marseille", "Nice", "Toulon"],
    "Hauts-de-France": ["Lille", "Amiens"],
    "Nouvelle-Aquitaine": ["Bordeaux", "La Rochelle", "Limoges"],
    "Occitanie": ["Toulouse", "Montpellier"],
}
CATEGORIES = {
    "Épicerie": (2, 15),
    "Boulangerie": (1, 8),
    "Boissons": (1, 20),
    "Hygiène": (2, 25),
    "Maison": (5, 80),
    "High-Tech": (20, 600),
}
CHANNELS = ["Magasin", "Web", "Click & Collect"]


def make_stores() -> pd.DataFrame:
    rows, sid = [], 1
    for region, cities in REGIONS.items():
        for city in cities:
            rows.append({"store_id": sid, "store_name": f"Store {city}", "city": city,
                         "region": region, "surface_m2": int(RNG.integers(400, 3000))})
            sid += 1
    return pd.DataFrame(rows)


def make_products(n: int = 300) -> pd.DataFrame:
    cats = RNG.choice(list(CATEGORIES), size=n, p=[.25, .15, .2, .15, .15, .1])
    prices = [round(float(RNG.uniform(*CATEGORIES[c])), 2) for c in cats]
    return pd.DataFrame({
        "product_id": range(1, n + 1),
        "product_name": [f"{c[:3].upper()}-{i:04d}" for i, c in enumerate(cats, 1)],
        "category": cats,
        "unit_price": prices,
        "unit_cost": [round(p * RNG.uniform(0.55, 0.8), 2) for p in prices],
    })


def make_customers(n: int = 8000) -> pd.DataFrame:
    return pd.DataFrame({
        "customer_id": range(1, n + 1),
        "gender": RNG.choice(["F", "M"], size=n),
        "age": RNG.integers(18, 80, size=n),
        "loyalty_member": RNG.random(n) < 0.4,
        "signup_date": pd.to_datetime("2022-01-01")
        + pd.to_timedelta(RNG.integers(0, 900, size=n), unit="D"),
    })


def make_orders(n: int, stores, products, customers) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    # Saisonnalité : pic en décembre et le samedi
    weights = np.array([1 + 0.6 * (d.month == 12) + 0.3 * (d.month in (6, 7)) + 0.4 * (d.dayofweek == 5)
                        for d in dates])
    weights /= weights.sum()
    # Clients "fidèles" commandent plus souvent (loi de Pareto)
    cust_w = RNG.pareto(1.5, len(customers)) + 1
    cust_w /= cust_w.sum()

    orders = pd.DataFrame({
        "order_id": range(1, n + 1),
        "order_date": RNG.choice(dates, size=n, p=weights),
        "customer_id": RNG.choice(customers.customer_id, size=n, p=cust_w),
        "store_id": RNG.choice(stores.store_id, size=n),
        "channel": RNG.choice(CHANNELS, size=n, p=[.6, .28, .12]),
    })
    n_lines = RNG.integers(1, 6, size=n)
    items = pd.DataFrame({
        "order_id": np.repeat(orders.order_id, n_lines),
        "product_id": RNG.choice(products.product_id, size=n_lines.sum()),
        "quantity": RNG.integers(1, 5, size=n_lines.sum()),
    })
    items = items.merge(products[["product_id", "unit_price"]], on="product_id")
    items["discount"] = np.where(RNG.random(len(items)) < 0.15, RNG.choice([.1, .2, .3], len(items)), 0.0)
    items.insert(0, "line_id", range(1, len(items) + 1))

    # Injecte quelques défauts de qualité pour la démonstration du nettoyage
    dirty = RNG.choice(items.index, size=int(len(items) * 0.005), replace=False)
    items.loc[dirty[: len(dirty) // 2], "quantity"] = -1
    items.loc[dirty[len(dirty) // 2:], "unit_price"] = np.nan
    return orders, items.sort_values("line_id")


def main(n_orders: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stores, products, customers = make_stores(), make_products(), make_customers()
    orders, items = make_orders(n_orders, stores, products, customers)
    for name, df in {"stores": stores, "products": products, "customers": customers,
                     "orders": orders, "order_items": items}.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:12s} {len(df):>8,} lignes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=50_000)
    main(parser.parse_args().orders)
