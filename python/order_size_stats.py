"""
Order size (items-per-order) statistical profile.

"Items per order" is this dataset's analogue of a logistics "units per
carton" metric: an order is the bundling/shipping unit, and n_items is how
many product units got packed into it. Computes the full descriptive
statistics suite -- mean, revenue-weighted mean, p25/median/p75, harmonic
mean, std dev, min, max -- overall and broken down by a few dimensions
that are actually actionable for packaging/pick-pack planning: distance
band, region, and order complexity (sellers per order).
"""

import numpy as np
import pandas as pd

from config import EXPORTS_DIR, REPORTS_DIR
from db import get_engine

RAW_SQL = """
    SELECT fd.order_id, fd.n_items, fd.total_price, fd.distance_band,
           fd.sellers_per_order_band, dc.region
    FROM gold.fact_delivery fd
    JOIN gold.dim_customer dc ON dc.customer_key = fd.customer_key
    WHERE fd.order_status NOT IN ('canceled', 'unavailable')
"""


def harmonic_mean(x: pd.Series) -> float:
    x = x[x > 0]
    return len(x) / np.sum(1.0 / x) if len(x) else float("nan")


def weighted_mean(x: pd.Series, w: pd.Series) -> float:
    w_sum = w.sum()
    return float(np.sum(x * w) / w_sum) if w_sum else float("nan")


def stats_row(x: pd.Series, w: pd.Series) -> dict:
    return {
        "n_orders": len(x),
        "mean": round(x.mean(), 4),
        "weighted_avg_by_revenue": round(weighted_mean(x, w), 4),
        "p25": round(x.quantile(0.25), 4),
        "median": round(x.median(), 4),
        "p75": round(x.quantile(0.75), 4),
        "harmonic_mean": round(harmonic_mean(x), 4),
        "std_dev": round(x.std(ddof=1), 4),
        "min": int(x.min()),
        "max": int(x.max()),
    }


def main():
    engine = get_engine()
    df = pd.read_sql(RAW_SQL, engine)

    overall = pd.DataFrame([stats_row(df["n_items"], df["total_price"])], index=["ALL ORDERS"])

    by_distance = df.groupby("distance_band").apply(
        lambda g: pd.Series(stats_row(g["n_items"], g["total_price"]))
    )
    by_region = df.groupby("region").apply(
        lambda g: pd.Series(stats_row(g["n_items"], g["total_price"]))
    )
    by_complexity = df.groupby("sellers_per_order_band").apply(
        lambda g: pd.Series(stats_row(g["n_items"], g["total_price"]))
    )

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    overall.to_csv(EXPORTS_DIR / "order_size_stats_overall.csv")
    by_distance.to_csv(EXPORTS_DIR / "order_size_stats_by_distance_band.csv")
    by_region.to_csv(EXPORTS_DIR / "order_size_stats_by_region.csv")
    by_complexity.to_csv(EXPORTS_DIR / "order_size_stats_by_seller_complexity.csv")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Order Size Statistics — Items per Order",
        "",
        "This dataset's analogue of a \"units per carton\" metric: an order is the "
        "bundling/shipping unit, `n_items` is how many product units were packed "
        "into it. Weighted average is weighted by order revenue (`total_price`), "
        f"n = {len(df):,} orders (cancelled/unavailable orders excluded, they have no items).",
        "",
        "## Overall",
        "",
        overall.to_markdown(),
        "",
        "## By distance band (seller → customer)",
        "",
        by_distance.to_markdown(),
        "",
        "## By customer region",
        "",
        by_region.to_markdown(),
        "",
        "## By order complexity (distinct sellers per order)",
        "",
        by_complexity.to_markdown(),
    ]
    (REPORTS_DIR / "order_size_stats.md").write_text("\n".join(lines), encoding="utf-8")

    print(overall.to_string())
    print(f"\nFull breakdowns written to reports/order_size_stats.md and data/exports/order_size_stats_*.csv")


if __name__ == "__main__":
    main()
