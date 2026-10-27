"""
Runs the full pipeline end to end, in dependency order, on one DuckDB
connection, and records per-stage timings in data/run_log.json.

    python -m src.pipeline            # incremental bronze, rebuild the rest
    python -m src.pipeline --force    # re-ingest every source file
"""

import argparse
import json
import time
from datetime import datetime, timezone

from src.analytics import (
    demand_variability, logistics_analysis, order_size_stats,
    risk_index, root_cause_analysis, seller_scorecard,
)
from src.config import get_settings
from src.dashboard import export_static
from src.db import connect
from src.ingestion import load_bronze
from src.models import delay_prediction
from src.quality import data_quality
from src.transformation import build_gold, build_silver


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-ingest all source files")
    args = parser.parse_args(argv)

    settings = get_settings()
    stages = [
        ("bronze_ingest", lambda con: load_bronze.ingest(con, settings, force=args.force)),
        ("bronze_quality_audit", lambda con: data_quality.run(con, settings)),
        ("silver_build", lambda con: build_silver.build(con, settings)),
        ("gold_build", lambda con: build_gold.build(con, settings)),
        ("seller_scorecard", lambda con: seller_scorecard.run(con, settings)),
        ("demand_variability", lambda con: demand_variability.run(con, settings)),
        ("logistics_analysis", lambda con: logistics_analysis.run(con, settings)),
        ("order_size_stats", lambda con: order_size_stats.run(con, settings)),
        ("risk_index", lambda con: risk_index.run(con, settings)),
        ("root_cause_analysis", lambda con: root_cause_analysis.run(con, settings)),
        ("delay_model", lambda con: delay_prediction.run(con, settings)),
        ("dashboard_export", lambda con: export_static.run(con, settings)),
    ]

    log = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stages": []}
    t_all = time.perf_counter()
    with connect(settings) as con:
        for name, fn in stages:
            t0 = time.perf_counter()
            fn(con)
            secs = time.perf_counter() - t0
            log["stages"].append({"stage": name, "seconds": round(secs, 2)})
            print(f"  {name:<24} {secs:6.1f}s")
    log["total_seconds"] = round(time.perf_counter() - t_all, 2)
    (settings.data_dir / "run_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Pipeline complete in {log['total_seconds']:.1f}s")


if __name__ == "__main__":
    main()
