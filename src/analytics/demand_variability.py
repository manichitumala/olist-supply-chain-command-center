"""
Demand variability by product category (weekly units sold).

v2 fixes:
  * Complete category x week grid, zero weeks included (v1 skipped them,
    understating volatility for sparse categories).
  * Only full weeks inside the analysis window (v1 included the near-empty
    2016 and Sep/Oct 2018 weeks, which produced spurious "drops").
  * Std dev uses ddof=1 consistently for CV and Z-scores (v1 mixed ddof=0/1).

Adds the Syntetos-Boylan classification used in inventory planning:
  ADI  = average interval between non-zero demand weeks
  CV2  = squared CV of the non-zero demand sizes
  Smooth (ADI<1.32, CV2<0.49) | Erratic (ADI<1.32, CV2>=0.49)
  Intermittent (ADI>=1.32, CV2<0.49) | Lumpy (ADI>=1.32, CV2>=0.49)
"""

import duckdb
import numpy as np
import pandas as pd

from src.config import Settings
from src.db import query_file

MIN_TOTAL_ITEMS = 100   # below this a category's CV is noise
Z_THRESHOLD = 2.0
ADI_CUT, CV2_CUT = 1.32, 0.49


def classify_cv(cv: float) -> str:
    if pd.isna(cv):
        return "Insufficient data"
    if cv < 0.5:
        return "Stable"
    if cv <= 1.0:
        return "Variable"
    return "Highly Variable"


def sbc_class(adi: float, cv2: float) -> str:
    if pd.isna(adi) or pd.isna(cv2):
        return "Insufficient data"
    if adi < ADI_CUT:
        return "Smooth" if cv2 < CV2_CUT else "Erratic"
    return "Intermittent" if cv2 < CV2_CUT else "Lumpy"


def add_z_scores(weekly: pd.DataFrame) -> pd.DataFrame:
    out = weekly.copy()
    g = out.groupby("category_en")["n_items_sold"]
    std = g.transform(lambda s: s.std(ddof=1))
    out["z_score"] = ((out["n_items_sold"] - g.transform("mean")) / std.replace(0, np.nan)).fillna(0.0)
    out["anomaly"] = np.select(
        [out["z_score"] > Z_THRESHOLD, out["z_score"] < -Z_THRESHOLD], ["Spike", "Drop"], "Normal")
    return out


def summarise(weekly: pd.DataFrame) -> pd.DataFrame:
    def per_category(s: pd.DataFrame) -> pd.Series:
        x = s["n_items_sold"].to_numpy()
        nonzero = x[x > 0]
        mean = x.mean()
        std = x.std(ddof=1) if len(x) > 1 else np.nan
        adi = len(x) / len(nonzero) if len(nonzero) else np.nan
        cv2 = (nonzero.std(ddof=1) / nonzero.mean()) ** 2 if len(nonzero) > 1 else np.nan
        return pd.Series({
            "n_weeks": len(x),
            "n_weeks_active": int((x > 0).sum()),
            "zero_week_share": round(1 - len(nonzero) / len(x), 3),
            "total_items": int(x.sum()),
            "total_revenue": round(s["revenue"].sum(), 2),
            "mean_weekly_demand": mean,
            "std_weekly_demand": std,
            "coefficient_of_variation": std / mean if mean > 0 else np.nan,
            "adi": adi,
            "cv2_nonzero": cv2,
            "anomaly_weeks": int((s["anomaly"] != "Normal").sum()),
        })

    summary = weekly.groupby("category_en")[["n_items_sold", "revenue", "anomaly"]] \
        .apply(per_category).reset_index()
    enough = summary["total_items"] >= MIN_TOTAL_ITEMS
    summary["demand_class"] = np.where(
        enough, summary["coefficient_of_variation"].map(classify_cv), "Insufficient data")
    summary["sbc_class"] = np.where(
        enough, [sbc_class(a, c) for a, c in zip(summary["adi"], summary["cv2_nonzero"])],
        "Insufficient data")
    summary["anomaly_frequency"] = (summary["anomaly_weeks"] / summary["n_weeks"]).round(3)
    return summary.sort_values(["coefficient_of_variation", "category_en"], ascending=[False, True])


def run(con: duckdb.DuckDBPyConnection, settings: Settings) -> pd.DataFrame:
    weekly = query_file(con, "kpis/05_demand_raw.sql")
    weekly["week_start"] = pd.to_datetime(weekly["week_start"])
    weekly = add_z_scores(weekly)

    summary = summarise(weekly)
    sufficient = set(summary.loc[summary["demand_class"] != "Insufficient data", "category_en"])
    anomalies = weekly[(weekly["anomaly"] != "Normal") & weekly["category_en"].isin(sufficient)] \
        .sort_values(["z_score", "category_en", "week_start"], ascending=[False, True, True])

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    summary.round(3).to_csv(settings.exports_dir / "demand_variability_by_category.csv", index=False)
    weekly.to_csv(settings.exports_dir / "demand_weekly_detail.csv", index=False)
    anomalies.to_csv(settings.exports_dir / "demand_anomalies.csv", index=False)

    write_report(summary, anomalies, weekly, settings)
    return summary


def write_report(summary, anomalies, weekly, settings: Settings) -> None:
    ok = summary[summary["demand_class"] != "Insufficient data"]
    cols = ["category_en", "total_items", "mean_weekly_demand", "coefficient_of_variation",
            "zero_week_share", "demand_class", "sbc_class", "anomaly_weeks"]
    lines = [
        "# Demand Variability Analysis",
        "",
        f"Weekly units sold for {summary.shape[0]} categories over "
        f"{weekly['week_start'].nunique()} full weeks "
        f"({weekly['week_start'].min():%Y-%m-%d} to {weekly['week_start'].max():%Y-%m-%d}), "
        "zero-sales weeks included. "
        f"{len(ok)} categories have >= {MIN_TOTAL_ITEMS} units and are classified.",
        "",
        "## CV classification",
        "",
        ok["demand_class"].value_counts().to_markdown(),
        "",
        "## Syntetos-Boylan classification (inventory-planning view)",
        "",
        ok["sbc_class"].value_counts().to_markdown(),
        "",
        "## 10 most volatile classified categories",
        "",
        ok.head(10)[cols].round(3).to_markdown(index=False),
        "",
        f"## Anomalous category-weeks (|Z| > {Z_THRESHOLD:g}): {len(anomalies)}",
        "",
        "Z-scores are measured against each category's whole-period mean, so in fast-growing "
        "categories later weeks lean toward 'Spike'. Trend-adjusted detection belongs to the "
        "forecasting phase.",
        "",
        anomalies.head(15)[["category_en", "week_start", "n_items_sold", "z_score", "anomaly"]]
        .assign(week_start=lambda d: d["week_start"].dt.date, z_score=lambda d: d["z_score"].round(2))
        .to_markdown(index=False),
    ]
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "demand_variability_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        summary = run(con, settings)
    print(summary["demand_class"].value_counts().to_string())


if __name__ == "__main__":
    main()
