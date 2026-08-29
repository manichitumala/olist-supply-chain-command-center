"""
Phase 4 - Geospatial logistics analysis.

Distance (already computed via Haversine in the gold layer SQL) is
correlated against delivery time, freight cost and review score, and
plotted as the classic distance/lead-time/freight/OTD scatter.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import CHARTS_DIR, EXPORTS_DIR, REPORTS_DIR, ROOT
from db import get_engine

SCATTER_SQL = (ROOT / "sql" / "kpis" / "03_logistics_kpis.sql").read_text(encoding="utf-8")
# The scatter-source query is the 3rd statement in the file; split on ';'
SCATTER_QUERY = SCATTER_SQL.split(";")[2]

OTD_COLORS = {"On Time": "#1baf7a", "Late": "#e34948"}


def main():
    engine = get_engine()

    with engine.connect() as conn:
        df = pd.read_sql(SCATTER_QUERY, conn)
        review_df = pd.read_sql("""
            SELECT avg_distance_km AS distance_km, review_score
            FROM gold.fact_delivery
            WHERE order_status = 'delivered' AND avg_distance_km IS NOT NULL
              AND review_score IS NOT NULL
        """, conn)

    correlations = {
        "distance_vs_delivery_time": df["distance_km"].corr(df["lead_time_days"]),
        "distance_vs_freight_cost": df["distance_km"].corr(df["freight_value"]),
        "distance_vs_review_score": review_df["distance_km"].corr(review_df["review_score"]),
    }

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 6))
    for status, color in OTD_COLORS.items():
        sub = df[df["otd_status"] == status]
        ax.scatter(
            sub["distance_km"], sub["lead_time_days"],
            s=(sub["freight_value"].clip(upper=150) / 2 + 8),
            alpha=0.25, c=color, label=status, edgecolors="none",
        )
    ax.set_xlabel("Seller-customer distance (km)")
    ax.set_ylabel("Delivery lead time (days)")
    ax.set_title("Distance vs delivery time (point size = freight cost)")
    ax.legend(title="Delivery status")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "distance_vs_delivery_scatter.png", dpi=130)
    plt.close(fig)

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.Series(correlations).round(4).to_csv(EXPORTS_DIR / "logistics_correlations.csv", header=["correlation"])

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Logistics / Geospatial Analysis",
        "",
        "Pearson correlations against Haversine seller-customer distance "
        f"(n={len(df):,} delivered orders):",
        "",
        f"- Distance vs delivery time: **r = {correlations['distance_vs_delivery_time']:.3f}**",
        f"- Distance vs freight cost: **r = {correlations['distance_vs_freight_cost']:.3f}**",
        f"- Distance vs review score: **r = {correlations['distance_vs_review_score']:.3f}**",
        "",
        "See `reports/charts/distance_vs_delivery_scatter.png` for the "
        "distance / lead-time / freight / OTD-status scatter plot.",
    ]
    (REPORTS_DIR / "logistics_analysis.md").write_text("\n".join(lines), encoding="utf-8")

    for k, v in correlations.items():
        print(f"{k}: {v:.4f}")


if __name__ == "__main__":
    main()
