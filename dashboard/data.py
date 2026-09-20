"""Data access. Reads the pipeline's tables once, caches them, and lets pandas do the filtering.

The app reads through a SQLAlchemy URL (config.SQLALCHEMY_URL), so the same code runs against
the bundled SQLite demo DB, MySQL, or Postgres. No dialect-specific SQL lives here.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

import config

DATE_COLS = ["disbursement_date", "last_pay_date", "extraction_date", "expected_completion_date"]
BOOL_COLS = ["watch_despite_good_standing", "plan_deviation_material_flag", "flag_cold", "flag_escalate"]

SNAPSHOT_COLS = [
    "extraction_date", "loan_no", "branch_code", "collection_champ_name", "loan_product_type_name",
    "days_in_arrears", "par_band", "outstanding_balance", "approved_amount", "interest_due",
    "interest_paid", "total_amount_received", "total_scheduled_repayment", "flag_cold",
    "disbursement_date",
]


@st.cache_resource
def _engine():
    return create_engine(config.SQLALCHEMY_URL, pool_pre_ping=True)


def _read(sql: str) -> pd.DataFrame:
    with _engine().connect() as conn:
        return pd.read_sql(text(sql), conn)


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c])
    for c in BOOL_COLS:
        if c in df.columns:
            df[c] = df[c].fillna(0).astype(bool)
    return df


@st.cache_data(ttl=600, show_spinner="Loading portfolio…")
def load_current() -> pd.DataFrame:
    return _tidy(_read("SELECT * FROM loans_current"))


@st.cache_data(ttl=600, show_spinner="Loading history…")
def load_snapshot() -> pd.DataFrame:
    return _tidy(_read(f"SELECT {', '.join(SNAPSHOT_COLS)} FROM loans_snapshot"))


@st.cache_data(ttl=600)
def load_run_log() -> pd.DataFrame:
    df = _read("SELECT run_id, started_at, finished_at, source_filename, extraction_date, "
               "rows_loaded, status, error_message FROM pipeline_run_log ORDER BY started_at DESC")
    for c in ("started_at", "finished_at", "extraction_date"):
        df[c] = pd.to_datetime(df[c])
    return df


def apply_filters(df: pd.DataFrame, branch=(), champ=(), product=()) -> pd.DataFrame:
    """Single place where the sidebar selection is applied - every panel goes through here."""
    m = pd.Series(True, index=df.index)
    if branch:
        m &= df["branch_code"].isin(branch)
    if champ:
        m &= df["collection_champ_name"].isin(champ)
    if product:
        m &= df["loan_product_type_name"].isin(product)
    return df[m]
