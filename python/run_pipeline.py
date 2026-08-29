"""
Runs the full medallion pipeline end-to-end, in dependency order:

  bronze -> data quality -> silver -> gold -> seller scorecard ->
  demand variability -> logistics analysis -> risk index ->
  root cause analysis -> dashboard data export

Each stage is also runnable standalone (e.g. `python data_quality.py`)
for iterating on one phase without re-loading everything.
"""

import time

import load_bronze
import data_quality
import build_silver
import build_gold
import seller_scorecard
import demand_variability
import logistics_analysis
import risk_index
import root_cause_analysis
import export_dashboard_data

STAGES = [
    ("Bronze layer load", load_bronze.main),
    ("Data quality report", data_quality.main),
    ("Silver layer build", build_silver.main),
    ("Gold star schema build", build_gold.main),
    ("Seller performance scorecard", seller_scorecard.main),
    ("Demand variability analysis", demand_variability.main),
    ("Logistics / geospatial analysis", logistics_analysis.main),
    ("Supply chain risk index", risk_index.main),
    ("Root cause analysis", root_cause_analysis.main),
    ("Dashboard data export", export_dashboard_data.main),
]


def main():
    for name, fn in STAGES:
        print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
        t0 = time.time()
        fn()
        print(f"[{name} done in {time.time() - t0:.1f}s]")
    print("\nPipeline complete. Open dashboard/index.html in a browser.")


if __name__ == "__main__":
    main()
