"""Central configuration for the Olist Supply Chain Command Center project."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Point this at wherever the raw Olist CSVs from Kaggle were extracted.
# The dataset is not committed to the repo (large + third-party license).
RAW_DATA_DIR = Path(os.environ.get(
    "OLIST_RAW_DIR",
    r"C:\Users\manic\Downloads\archive (1)",
))

REPORTS_DIR = ROOT / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
EXPORTS_DIR = ROOT / "data" / "exports"
DASHBOARD_DIR = ROOT / "dashboard"

DB_CONFIG = {
    "host": os.environ.get("OLIST_DB_HOST", "localhost"),
    "port": int(os.environ.get("OLIST_DB_PORT", "5432")),
    "dbname": os.environ.get("OLIST_DB_NAME", "olist_scm"),
    "user": os.environ.get("OLIST_DB_USER", "postgres"),
    "password": os.environ.get("OLIST_DB_PASSWORD", ""),
}

SQLALCHEMY_URL = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)
