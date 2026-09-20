"""
Central configuration for the loan portfolio pipeline.

Nothing here is hardcoded to a specific machine — everything either has a
sensible relative default or is read from environment variables, so this
runs the same on your laptop, a server, or a scheduled task without editing
code each time.

Set these in a `.env` file (see .env.example) or as real environment
variables before running the pipeline.
"""
import os
from pathlib import Path

# ----------------------------------------------------------------------------
# Folder layout — all relative to wherever this pipeline lives.
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = Path(os.environ.get("LOAN_PIPELINE_RAW_DIR", BASE_DIR / "raw"))
PROCESSED_DIR = Path(os.environ.get("LOAN_PIPELINE_PROCESSED_DIR", BASE_DIR / "processed"))
DASHBOARD_DIR = Path(os.environ.get("LOAN_PIPELINE_DASHBOARD_DIR", BASE_DIR / "dashboard"))
ARCHIVE_DIR = Path(os.environ.get("LOAN_PIPELINE_ARCHIVE_DIR", BASE_DIR / "raw" / "_archive"))

for d in (RAW_DIR, PROCESSED_DIR, DASHBOARD_DIR, ARCHIVE_DIR):
    d.mkdir(parents=True, exist_ok=True)

DASHBOARD_HTML_PATH = DASHBOARD_DIR / "dashboard.html"

# ----------------------------------------------------------------------------
# MySQL connection — read from environment, never hardcoded.
# ----------------------------------------------------------------------------
MYSQL_HOST = os.environ.get("LOAN_DB_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("LOAN_DB_PORT", "3306"))
MYSQL_USER = os.environ.get("LOAN_DB_USER", "root")
MYSQL_PASSWORD = os.environ.get("LOAN_DB_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("LOAN_DB_NAME", "loan_portfolio")

# LOAN_DB_URL overrides everything above with any SQLAlchemy URL, e.g. the bundled demo DB:
#   sqlite:///data/loan_portfolio.db        (default for the deployed demo)
#   postgresql+psycopg2://user:pw@host/db   (only needs a Postgres dialect of schema.sql)
_DEFAULT_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
)
SQLALCHEMY_URL = os.environ.get("LOAN_DB_URL") or _DEFAULT_URL

# ----------------------------------------------------------------------------
# Materiality threshold for the "behind plan" flag.
# See notebook finding: raw plan_deviation was ~KES 1 for 100% of loans
# (interest rounding), so we only flag genuine drift above this bound.
# ----------------------------------------------------------------------------
PLAN_DEVIATION_MATERIALITY_KES = float(
    os.environ.get("LOAN_PLAN_DEVIATION_MATERIALITY", "50")
)

# ----------------------------------------------------------------------------
# Cold / escalate thresholds (days since last payment)
# ----------------------------------------------------------------------------
COLD_THRESHOLD_DAYS = int(os.environ.get("LOAN_COLD_THRESHOLD_DAYS", "7"))
ESCALATE_THRESHOLD_DAYS = int(os.environ.get("LOAN_ESCALATE_THRESHOLD_DAYS", "30"))
