"""
Order size (items per order) statistical profile - this dataset's analogue
of a "units per carton" metric. Full descriptive suite (mean, revenue-
weighted mean, quartiles, harmonic mean, std dev, min, max), overall and by
distance band, customer region and order complexity.
"""

import duckdb
import numpy as np
import pandas as pd

from src.config import Settings

RAW_SQL = """
    SELECT order_id, n_items, items_value AS total_price, distance_band,
           sellers_per_order_band, customer_region AS region
    FROM gold.fact_order
    WHERE is_revenue_order
"""


def harmonic_mean(x: pd.Series) -> float:
    x = x[x > 0]
    return len(x) / np.sum(1.0 / x) if len(x) else float("nan")


def weighted_mean(x: pd.Series, w: pd.Series) -> float:
    return float(np.sum(x * w) / w.sum()) if w.sum() else float("nan")


def stats_row(x: pd.Series, w: pd.Series) -> dict:
    return {
        "n_orders": len(x),
        "mean": round(x.mean(), 4),
        "weighted_avg_by_revenue": round(weighted_mean(x, w), 4),
        "p25": x.quantile(0.25),
        "median": x.median(),
        "p75": x.quantile(0.75),
        "harmonic_mean": round(harmonic_mean(x), 4),
        "std_dev": round(x.std(ddof=1), 4),
        "min": int(x.min()),
        "max": int(x.max()),
    }


def breakdown(df: pd.DataFrame, by: str) -> pd.DataFrame:
    return pd.DataFrame({k: stats_row(g["n_items"], g["total_price"])
                         for k, g in df.groupby(by)}).T.rename_axis(by)


def run(con: duckdb.DuckDBPyConnection, settings: Settings) -> pd.DataFrame:
    df = con.execute(RAW_SQL).df()
    overall = pd.DataFrame([stats_row(df["n_items"], df["total_price"])], index=["ALL ORDERS"])
    parts = {
        "distance_band": breakdown(df, "distance_band"),
        "region": breakdown(df, "region"),
        "seller_complexity": breakdown(df, "sellers_per_order_band"),
    }

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    overall.to_csv(settings.exports_dir / "order_size_stats_overall.csv")
    parts["distance_band"].to_csv(settings.exports_dir / "order_size_stats_by_distance_band.csv")
    parts["region"].to_csv(settings.exports_dir / "order_size_stats_by_region.csv")
    parts["seller_complexity"].to_csv(settings.exports_dir / "order_size_stats_by_seller_complexity.csv")

    lines = [
        "# Order Size Statistics - Items per Order",
        "",
        "An order is the bundling/shipping unit; `n_items` is how many product units it held. "
        f"Weighted average is weighted by order item value. n = {len(df):,} orders "
        "(cancelled/unavailable orders and orders with no items excluded).",
        "",
        "## Overall", "", overall.to_markdown(), "",
        "## By distance band (seller -> customer)", "", parts["distance_band"].to_markdown(), "",
        "## By customer region", "", parts["region"].to_markdown(), "",
        "## By order complexity (distinct sellers per order)", "", parts["seller_complexity"].to_markdown(),
    ]
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "order_size_stats.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return overall


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        print(run(con, settings).to_string())


if __name__ == "__main__":
    main()
