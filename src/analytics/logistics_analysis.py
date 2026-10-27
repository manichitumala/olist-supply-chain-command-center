"""
Geospatial logistics analysis: seller-customer Haversine distance against
lead time, freight cost and review score. Reports Spearman alongside Pearson
because lead times and freight are heavily right-skewed.
"""

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import Settings  # noqa: E402
from src.db import query_file  # noqa: E402

OTD_COLORS = {"On Time": "#1baf7a", "Late": "#e34948"}
PAIRS = [("lead_time_days", "delivery time"), ("freight_value", "freight cost"),
         ("review_score", "review score")]


def correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, label in PAIRS:
        sub = df[["distance_km", col]].dropna()
        rows.append({
            "pair": f"distance_vs_{label.replace(' ', '_')}",
            "n": len(sub),
            "pearson_r": sub["distance_km"].corr(sub[col], method="pearson"),
            "spearman_rho": sub["distance_km"].corr(sub[col], method="spearman"),
        })
    return pd.DataFrame(rows)


def run(con: duckdb.DuckDBPyConnection, settings: Settings) -> pd.DataFrame:
    df = query_file(con, "kpis/03_logistics_kpis.sql", 2)
    bands = query_file(con, "kpis/03_logistics_kpis.sql", 0)
    corr = correlations(df)

    settings.charts_dir.mkdir(parents=True, exist_ok=True)
    sample = df.sample(n=min(20000, len(df)), random_state=42)
    fig, ax = plt.subplots(figsize=(9, 6))
    for status, color in OTD_COLORS.items():
        sub = sample[sample["otd_status"] == status]
        ax.scatter(sub["distance_km"], sub["lead_time_days"],
                   s=(sub["freight_value"].clip(upper=150) / 2 + 8),
                   alpha=0.25, c=color, label=status, edgecolors="none")
    ax.set_xlabel("Seller-customer distance (km)")
    ax.set_ylabel("Delivery lead time (days)")
    ax.set_title("Distance vs delivery time (point size = freight cost, 20k-order sample)")
    ax.legend(title="Delivery status")
    fig.tight_layout()
    fig.savefig(settings.charts_dir / "distance_vs_delivery_scatter.png", dpi=130)
    plt.close(fig)

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    corr.round(4).to_csv(settings.exports_dir / "logistics_correlations.csv", index=False)

    lines = [
        "# Logistics / Geospatial Analysis",
        "",
        "Correlations against Haversine seller-customer distance (zip-prefix centroids), "
        "delivered orders:",
        "",
        corr.round(3).to_markdown(index=False),
        "",
        "## Late rate by distance band",
        "",
        bands.to_markdown(index=False),
        "",
        "See `reports/charts/distance_vs_delivery_scatter.png`.",
    ]
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "logistics_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return corr


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        print(run(con, settings).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
