"""
Data access for the Streamlit dashboard.

Reads the gold Parquet files (data/gold) through an in-memory DuckDB
connection, plus the analysis exports (data/exports). The dashboard never
touches the warehouse file, so it can run while the pipeline rebuilds.
"""

from dataclasses import dataclass
from datetime import date

import duckdb
import pandas as pd

from src.analytics.stats import wilson_interval
from src.config import Settings

GOLD_TABLES = ["fact_order", "fact_order_item", "fact_seller_order", "dim_product",
               "dim_seller", "dim_customer", "analysis_window"]


@dataclass(frozen=True)
class Filters:
    regions: tuple[str, ...]          # empty = all
    start: date
    end: date

    def where(self, alias: str = "") -> tuple[str, list]:
        p = f"{alias}." if alias else ""
        sql = f"CAST({p}purchase_ts AS DATE) BETWEEN ? AND ?"
        params: list = [self.start, self.end]
        if self.regions:
            sql += f" AND {p}customer_region IN ({', '.join('?' * len(self.regions))})"
            params += list(self.regions)
        return sql, params


def missing_inputs(settings: Settings) -> list[str]:
    missing = [f"data/gold/{t}.parquet" for t in GOLD_TABLES
               if not (settings.gold_dir / f"{t}.parquet").exists()]
    for f in ["seller_scorecard.csv", "demand_weekly_detail.csv",
              "demand_variability_by_category.csv", "supply_chain_risk_index.csv",
              "root_cause_transport_delay.csv"]:
        if not (settings.exports_dir / f).exists():
            missing.append(f"data/exports/{f}")
    return missing


def connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for t in GOLD_TABLES:
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{(settings.gold_dir / f'{t}.parquet').as_posix()}'")
    return con


def analysis_window(con) -> tuple[date, date]:
    return con.execute("SELECT start_date, end_date FROM analysis_window").fetchone()


def regions(con) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT DISTINCT customer_region FROM fact_order WHERE customer_region IS NOT NULL ORDER BY 1"
    ).fetchall()]


def headline(con, f: Filters) -> dict:
    where, params = f.where()
    return con.execute(f"""
        SELECT COUNT(*) AS orders,
               COUNT(DISTINCT customer_unique_id) AS customers,
               SUM(CASE WHEN is_revenue_order THEN items_value END) AS gmv,
               100.0 * AVG(CASE WHEN is_delivered THEN (otd_status = 'On Time')::INT END) AS otd_pct,
               SUM(is_delivered::INT) AS delivered,
               SUM((otd_status = 'Late')::INT) AS late,
               AVG(lead_time_days) AS lead_days,
               100.0 * AVG(is_canceled::INT) AS cancel_pct,
               AVG(review_score) AS review
        FROM fact_order WHERE {where}""", params).df().iloc[0].to_dict()


def monthly(con, f: Filters) -> pd.DataFrame:
    where, params = f.where()
    return con.execute(f"""
        SELECT date_trunc('month', purchase_ts)::DATE AS month,
               COUNT(*) AS orders,
               SUM(is_delivered::INT) AS delivered,
               SUM((otd_status = 'Late')::INT) AS late,
               SUM(CASE WHEN is_revenue_order THEN items_value END) AS gmv,
               AVG(review_score) AS review
        FROM fact_order WHERE {where}
        GROUP BY 1 ORDER BY 1""", params).df().pipe(_with_rate, "late", "delivered")


def stage_by_status(con, f: Filters) -> pd.DataFrame:
    where, params = f.where()
    return con.execute(f"""
        SELECT otd_status, COUNT(*) AS orders,
               AVG(payment_time_hours) / 24 AS "Payment",
               AVG(fulfilment_time_hours) / 24 AS "Seller fulfilment",
               AVG(transit_time_hours) / 24 AS "Transit"
        FROM fact_order
        WHERE is_delivered AND is_valid_for_lead_time_analysis AND {where}
        GROUP BY 1""", params).df()


def monthly_stages(con, f: Filters) -> pd.DataFrame:
    where, params = f.where()
    return con.execute(f"""
        SELECT date_trunc('month', purchase_ts)::DATE AS month,
               AVG(payment_time_hours) / 24 AS "Payment",
               AVG(fulfilment_time_hours) / 24 AS "Seller fulfilment",
               AVG(transit_time_hours) / 24 AS "Transit"
        FROM fact_order
        WHERE is_delivered AND is_valid_for_lead_time_analysis AND {where}
        GROUP BY 1 ORDER BY 1""", params).df()


DISTANCE_ORDER = ["0-100 km", "100-300 km", "300-500 km", "500-1000 km", "1000+ km"]


def late_by_distance(con, f: Filters) -> pd.DataFrame:
    where, params = f.where()
    df = con.execute(f"""
        SELECT distance_band, COUNT(*) AS delivered, SUM((otd_status = 'Late')::INT) AS late,
               AVG(freight_value) AS freight
        FROM fact_order WHERE is_delivered AND distance_band <> 'Unknown' AND {where}
        GROUP BY 1""", params).df()
    df["distance_band"] = pd.Categorical(df["distance_band"], DISTANCE_ORDER, ordered=True)
    return df.sort_values("distance_band").pipe(_with_rate, "late", "delivered")


def late_by_state(con, f: Filters, min_orders: int = 30) -> pd.DataFrame:
    where, params = f.where()
    return con.execute(f"""
        SELECT customer_state AS state, customer_region AS region,
               COUNT(*) AS delivered, SUM((otd_status = 'Late')::INT) AS late,
               AVG(lead_time_days) AS lead_days, AVG(review_score) AS review
        FROM fact_order WHERE is_delivered AND {where}
        GROUP BY 1, 2 HAVING COUNT(*) >= ?""", params + [min_orders]).df() \
        .pipe(_with_rate, "late", "delivered").sort_values("rate", ascending=False)


def _with_rate(df: pd.DataFrame, k: str, n: str) -> pd.DataFrame:
    df = df.copy()
    lo, hi = wilson_interval(df[k], df[n])
    df["rate"] = 100 * df[k] / df[n]
    df["ci_low"], df["ci_high"] = 100 * lo, 100 * hi
    return df


def layer_counts(settings: Settings) -> pd.DataFrame:
    con = duckdb.connect()
    rows = []
    for layer, folder in [("Bronze", settings.bronze_dir), ("Silver", settings.silver_dir),
                          ("Gold", settings.gold_dir)]:
        for p in sorted(folder.glob("*.parquet")):
            n = con.execute(f"SELECT COUNT(*) FROM '{p.as_posix()}'").fetchone()[0]
            rows.append({"layer": layer, "table": p.stem, "rows": n,
                         "size_mb": round(p.stat().st_size / 1e6, 2)})
    return pd.DataFrame(rows)


def read_export(settings: Settings, name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(settings.exports_dir / name, **kw)
