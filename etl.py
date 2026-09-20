
from __future__ import annotations

import re
import sys
import logging
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("etl")

MONEY_COLS = [
    "Amount in Arrears", "Net Balance", "Repayment", "Approved Amount", "Requested Amount",
    "Savings Balance", "Security Amount", "Current Scheduled Interest", "Interest Paid",
    "Interest Due", "Principle Repayment", "Principal Paid", "Outstanding Balance",
    "Outstanding Interest", "Repo Fee Due", "Repo Fee Balance", "Tracking Fee Repair Balance",
    "Tracking Fee Balance", "Total Outstanding Balance", "Total Amount Received",
    "Total Scheduled Repayment", "Excess Amount Paid", "Savingbalance",
    "Schedule Principal Repayments", "Scheduled Interest", "Total Interest Paid",
    "Total Interest Charged", "Schedule Interest Paid", "Schedule Interest Balance",
    "Excess Interest Charged", "Excess Interest Paid", "Excess Interest Balance",
    "Schedule Net Balance",
]

DATE_COLS = [
    "Application Date", "Disbursement Date", "Repayment Start Date",
    "Expected Date of Completion", "Interest Due Date", "Interest Posting Date",
    "Next Run Date", "Last Pay Date", "Penalty Posting Date",
]

TEXT_COLS_TO_CLEAN = [
    "Member Name", "Stage Name", "Collection Champ Name", "Collection Troops Name",
]



def resolve_extraction_date(filepath: Path) -> date:
    """Best-effort: filename date pattern > file mtime > today."""
    # look for YYYY-MM-DD or YYYYMMDD in the filename
    m = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", filepath.stem)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    try:
        mtime = filepath.stat().st_mtime
        return datetime.fromtimestamp(mtime).date()
    except OSError:
        log.warning("Could not read file mtime, falling back to today's date.")
        return datetime.now().date()



def clean_text_series(s: pd.Series) -> pd.Series:
    s = s.astype(str)
    s = s.str.replace(r"&nbsp;?", " ", regex=True)
    s = s.str.replace(r"\s+", " ", regex=True)
    s = s.str.strip()
    return s


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")


def extract_and_clean(filepath: Path) -> pd.DataFrame:
    log.info(f"Reading {filepath}")
    df = pd.read_csv(filepath)
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]  # strip BOM on first col

    for c in MONEY_COLS:
        if c in df.columns:
            df[c] = to_num(df[c])

    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], format="%m/%d/%Y", errors="coerce")

    for c in TEXT_COLS_TO_CLEAN:
        if c in df.columns:
            df[c] = clean_text_series(df[c])

    # drop columns confirmed 100% empty in source
    fully_empty = [c for c in ("Loan Repayment Account", "Batch No.", "Pin Number") if c in df.columns]
    if fully_empty:
        df = df.drop(columns=fully_empty)

    return df


def engineer_features(df: pd.DataFrame, extraction_date: date) -> pd.DataFrame:
    df = df.copy()

    # PAR band — kept as the source system's native labels per decision, not relabeled.
    df["par_band"] = np.select(
        [
            df["Days in Arrears"] == 0,
            df["Days in Arrears"] == 1,
            df["Days in Arrears"] == 2,
            df["Days in Arrears"] == 3,
            df["Days in Arrears"] >= 4,
        ],
        ["Performing", "Watch", "Substandard", "Doubtful", "Loss"],
        default="Unknown",
    )
    df["is_at_risk"] = df["Days in Arrears"] > 0
    # Loss severity sub-band — only meaningful where par_band == "Loss"
    loss_bins = [3, 30, 90, 180, 365, np.inf]
    loss_labels = ["4-30d", "31-90d", "91-180d", "181-365d", "365d+"]
    df["loss_severity"] = (
        pd.cut(df["Days in Arrears"].where(df["par_band"] == "Loss"),
               bins=loss_bins, labels=loss_labels)
        .astype(object)
        .where(df["par_band"] == "Loss", None)
    )

    # Watch despite good standing — 0 DPD today, but PAR AVG above THIS
    # snapshot's own 75th percentile (recomputed per run, not a fixed constant,
    # matching the exploration notebook's logic).
    par_avg_p75 = df["PAR AVG"].quantile(0.75)
    df["watch_despite_good_standing"] = (
        (df["Days in Arrears"] == 0) & (df["PAR AVG"] > par_avg_p75)
    )

    # Collateral coverage
    df["collateral_coverage"] = np.where(
        df["Approved Amount"] > 0,
        df["Security Amount"] / df["Approved Amount"],
        np.nan,
    )
    df["under_collateralized"] = df["collateral_coverage"] < 1.0
    df["repossessed"] = df.get("Re-Po Fee Count", 0) > 0

    # Plan deviation — with materiality threshold (fix vs. notebook, which
    # flagged 100% of loans due to ~KES 1 interest-rounding noise).
    df["plan_deviation"] = df["Net Balance"] - df["Schedule Net Balance"]
    df["plan_deviation_material_flag"] = (
        df["plan_deviation"] > config.PLAN_DEVIATION_MATERIALITY_KES
    )

    # Collection efficiency
    df["collection_efficiency_pct"] = np.where(
        df["Total Scheduled Repayment"] > 0,
        df["Total Amount Received"] / df["Total Scheduled Repayment"] * 100,
        np.nan,
    )

    # Days since last payment, cold/escalate flags
    extraction_ts = pd.Timestamp(extraction_date)
    df["days_since_last_pay"] = (extraction_ts - df["Last Pay Date"]).dt.days
    df["flag_cold"] = df["days_since_last_pay"] > config.COLD_THRESHOLD_DAYS
    df["flag_escalate"] = df["days_since_last_pay"] > config.ESCALATE_THRESHOLD_DAYS

    # Yield
    df["loan_yield_pct"] = np.where(
        df["Approved Amount"] > 0,
        df["Interest Due"] / df["Approved Amount"] * 100,
        np.nan,
    )

    df["extraction_date"] = extraction_date
    return df



def to_db_frame(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "Member No.": "member_no", "Member Name": "member_name", "Loan No.": "loan_no",
        "Phone Number": "phone_number", "Car Registration Number": "car_registration_number",
        "Stage Name": "stage_name", "Branch Code": "branch_code",
        "Collection Champ Name": "collection_champ_name", "Collection Champion": "collection_champion",
        "Collection Troops": "collection_troops", "Collection Troops Name": "collection_troops_name",
        "Loan Product Type": "loan_product_type", "Loan Product Type Name": "loan_product_type_name",
        "Asset Type": "asset_type", "Motor Bike Type": "motor_bike_type",
        "Application Date": "application_date", "Disbursement Date": "disbursement_date",
        "Repayment Start Date": "repayment_start_date",
        "Expected Date of Completion": "expected_completion_date", "Last Pay Date": "last_pay_date",
        "Days in Arrears": "days_in_arrears", "Performance Category": "performance_category",
        "PAR AVG": "par_avg", "Approved Amount": "approved_amount",
        "Outstanding Balance": "outstanding_balance",
        "Total Outstanding Balance": "total_outstanding_balance",
        "Amount in Arrears": "amount_in_arrears", "Net Balance": "net_balance",
        "Schedule Net Balance": "schedule_net_balance", "Security Amount": "security_amount",
        "Savings Balance": "savings_balance", "Interest Due": "interest_due",
        "Interest Paid": "interest_paid", "Total Amount Received": "total_amount_received",
        "Total Scheduled Repayment": "total_scheduled_repayment",
        "Re-Po Fee Count": "repo_fee_count", "Installments": "installments",
    }
    keep_engineered = [
        "par_band", "collateral_coverage", "plan_deviation", "plan_deviation_material_flag",
        "days_since_last_pay", "flag_cold", "flag_escalate", "collection_efficiency_pct",
        "loss_severity", "watch_despite_good_standing",
        "extraction_date",
    ]
    cols_present = {k: v for k, v in rename_map.items() if k in df.columns}
    out = df[list(cols_present.keys()) + keep_engineered].rename(columns=cols_present)
    return out



def load_to_mysql(db_df: pd.DataFrame, source_filename: str) -> int:
    engine = create_engine(config.SQLALCHEMY_URL)
    started_at = datetime.now()

    with engine.begin() as conn:
        db_df.to_sql("loans_snapshot", conn, if_exists="append", index=False,
                      method="multi", chunksize=500)

        conn.execute(text("DELETE FROM loans_current"))
        db_df.to_sql("loans_current", conn, if_exists="append", index=False,
                      method="multi", chunksize=500)

        conn.execute(
            text("""
                INSERT INTO pipeline_run_log
                    (started_at, finished_at, source_filename, extraction_date, rows_loaded, status)
                VALUES (:started, :finished, :fname, :extraction_date, :rows, 'success')
            """),
            {
                "started": started_at,
                "finished": datetime.now(),
                "fname": source_filename,
                "extraction_date": db_df["extraction_date"].iloc[0],
                "rows": len(db_df),
            },
        )
    log.info(f"Loaded {len(db_df)} rows into loans_snapshot + loans_current.")
    return len(db_df)



def run(filepath: str) -> pd.DataFrame:
    path = Path(filepath)
    extraction_date = resolve_extraction_date(path)
    log.info(f"Resolved extraction_date = {extraction_date}")

    raw = extract_and_clean(path)
    engineered = engineer_features(raw, extraction_date)

    processed_path = config.PROCESSED_DIR / f"loans_engineered_{extraction_date}.csv"
    engineered.to_csv(processed_path, index=False)
    log.info(f"Wrote cleaned/engineered file to {processed_path}")

    db_df = to_db_frame(engineered)

    try:
        load_to_mysql(db_df, path.name)
    except Exception as e:
        log.error(f"MySQL load failed: {e}")
        log.error(
            "The cleaned CSV was still written to disk above, so no data is "
            "lost — fix the DB connection (see config.py / .env) and re-run "
            "against that file, or just re-run this script once MySQL is reachable."
        )
        raise

    return engineered


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python etl.py path/to/loans_export.csv")
        sys.exit(1)
    run(sys.argv[1])
