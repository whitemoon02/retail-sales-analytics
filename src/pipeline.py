"""Pipeline d'analyse : nettoyage -> modèle en étoile SQLite -> KPI SQL -> segmentation RFM -> graphiques.

Usage : python src/pipeline.py
"""
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, PROCESSED = ROOT / "data" / "raw", ROOT / "data" / "processed"
DB = PROCESSED / "retail.db"
FIG = ROOT / "reports" / "figures"


def load_raw() -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_csv(p) for p in RAW.glob("*.csv")}


def clean(dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    items = dfs["order_items"].copy()
    before = len(items)
    items = items[(items.quantity > 0) & items.unit_price.notna()].drop_duplicates("line_id")
    print(f"Nettoyage order_items : {before - len(items)} lignes invalides supprimées")
    items["revenue"] = (items.quantity * items.unit_price * (1 - items.discount)).round(2)

    orders = dfs["orders"].copy()
    orders["order_date"] = pd.to_datetime(orders.order_date)
    orders = orders[orders.order_id.isin(items.order_id)]
    return {**dfs, "order_items": items, "orders": orders}


def build_star_schema(dfs: dict[str, pd.DataFrame]) -> None:
    """Fact table fact_sales + dimensions, prête pour Power BI."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    fact = (dfs["order_items"]
            .merge(dfs["orders"], on="order_id")
            .merge(dfs["products"][["product_id", "unit_cost"]], on="product_id"))
    fact["margin"] = (fact.revenue - fact.quantity * fact.unit_cost).round(2)
    fact["date_key"] = fact.order_date.dt.strftime("%Y%m%d").astype(int)

    dates = pd.date_range(fact.order_date.min(), fact.order_date.max())
    dim_date = pd.DataFrame({
        "date_key": dates.strftime("%Y%m%d").astype(int), "date": dates.date,
        "year": dates.year, "quarter": dates.quarter, "month": dates.month,
        "month_name": dates.strftime("%b"), "weekday": dates.dayofweek + 1,
    })
    with sqlite3.connect(DB) as con:
        fact.drop(columns=["unit_cost"]).to_sql("fact_sales", con, if_exists="replace", index=False)
        dim_date.to_sql("dim_date", con, if_exists="replace", index=False)
        for d in ("products", "customers", "stores"):
            dfs[d].to_sql(f"dim_{d[:-1]}", con, if_exists="replace", index=False)
    # Exports CSV pour import direct dans Power BI / Tableau
    fact.to_csv(PROCESSED / "fact_sales.csv", index=False)
    dim_date.to_csv(PROCESSED / "dim_date.csv", index=False)


def run_sql_kpis() -> dict[str, pd.DataFrame]:
    sql = (ROOT / "sql" / "kpi_queries.sql").read_text(encoding="utf-8")
    results = {}
    with sqlite3.connect(DB) as con:
        for block in sql.split("-- name:")[1:]:
            name, query = block.split("\n", 1)
            results[name.strip()] = pd.read_sql(query, con)
    return results


def rfm_segmentation(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    sales = dfs["order_items"].groupby("order_id", as_index=False).revenue.sum().merge(dfs["orders"])
    ref = sales.order_date.max() + pd.Timedelta(days=1)
    rfm = sales.groupby("customer_id").agg(
        recency=("order_date", lambda d: (ref - d.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("revenue", "sum"))
    rfm["R"] = pd.qcut(rfm.recency, 4, labels=[4, 3, 2, 1]).astype(int)
    rfm["F"] = pd.qcut(rfm.frequency.rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["M"] = pd.qcut(rfm.monetary, 4, labels=[1, 2, 3, 4]).astype(int)

    def segment(r):
        if r.R >= 3 and r.F >= 3:
            return "Champions"
        if r.F >= 3:
            return "Fidèles à risque"
        if r.R >= 3:
            return "Nouveaux / prometteurs"
        return "Endormis"
    rfm["segment"] = rfm.apply(segment, axis=1)
    rfm.to_csv(PROCESSED / "rfm_segments.csv")
    return rfm


def plot(kpis: dict[str, pd.DataFrame], rfm: pd.DataFrame) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    m = kpis["monthly_revenue"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(m.month, m.revenue / 1e3, marker="o", color="#1f5f8b")
    ax.set(title="Chiffre d'affaires mensuel (k€)", ylabel="k€")
    ax.tick_params(axis="x", rotation=60)
    fig.tight_layout(); fig.savefig(FIG / "ca_mensuel.png", dpi=120); plt.close(fig)

    c = kpis["category_performance"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(c.category, c.revenue / 1e3, color="#1f5f8b")
    ax.set(title="CA par catégorie (k€)", xlabel="k€"); ax.invert_yaxis()
    fig.tight_layout(); fig.savefig(FIG / "ca_categorie.png", dpi=120); plt.close(fig)

    s = rfm.groupby("segment").agg(clients=("R", "size"), ca=("monetary", "sum"))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(s.index, s.ca / s.ca.sum() * 100, color="#2e8b57")
    for i, (n, v) in enumerate(zip(s.clients, s.ca / s.ca.sum() * 100)):
        ax.text(i, v + 1, f"{n} clients", ha="center", fontsize=8)
    ax.set(title="Part du CA par segment RFM (%)", ylabel="%")
    fig.tight_layout(); fig.savefig(FIG / "segments_rfm.png", dpi=120); plt.close(fig)


def main() -> None:
    dfs = clean(load_raw())
    build_star_schema(dfs)
    kpis = run_sql_kpis()
    rfm = rfm_segmentation(dfs)
    plot(kpis, rfm)
    print("\n=== KPI globaux ===")
    print(kpis["global_kpis"].T.to_string(header=False))
    print("\n=== Top 5 magasins ===")
    print(kpis["store_ranking"].head().to_string(index=False))
    print(f"\nFigures : {FIG}\nBase : {DB}")


if __name__ == "__main__":
    main()
