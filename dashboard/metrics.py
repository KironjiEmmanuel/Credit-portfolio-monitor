"""Portfolio metrics. Formulas are the ones validated in the exploration notebooks - unchanged."""
from __future__ import annotations

import pandas as pd

PAR_BANDS = ["Performing", "Watch", "Substandard", "Doubtful", "Loss"]
LOSS_SEVERITY = ["4-30d", "31-90d", "91-180d", "181-365d", "365d+"]

# Illustrative state thresholds for the headline PAR figure (shown next to the number in the UI).
PAR_HEALTHY_BELOW = 10.0
PAR_HIGH_ABOVE = 20.0

EARLY_DEFAULT_DAYS = 60


def _safe_pct(num: float, den: float) -> float:
    return float(num) / float(den) * 100 if den else 0.0


def par_pct(df: pd.DataFrame) -> float:
    """Share of outstanding principal on loans with any days in arrears."""
    at_risk = df.loc[df["days_in_arrears"] > 0, "outstanding_balance"].sum()
    return _safe_pct(at_risk, df["outstanding_balance"].sum())


def kpis(df: pd.DataFrame) -> dict:
    return {
        "loans": len(df),
        "outstanding": float(df["outstanding_balance"].sum()),
        "par": par_pct(df),
        "ce": _safe_pct(df["total_amount_received"].sum(), df["total_scheduled_repayment"].sum()),
        "yield_expected": _safe_pct(df["interest_due"].sum(), df["approved_amount"].sum()),
        "yield_realized": _safe_pct(df["interest_paid"].sum(), df["approved_amount"].sum()),
        "realization": _safe_pct(df["interest_paid"].sum(), df["interest_due"].sum()),
    }


def par_state(par: float) -> tuple[str, str]:
    """(label, badge colour). Colour encodes state only."""
    if par < PAR_HEALTHY_BELOW:
        return "Healthy", "green"
    if par <= PAR_HIGH_ABOVE:
        return "Elevated", "orange"
    return "High", "red"


def history(snap: pd.DataFrame) -> pd.DataFrame:
    """One row per snapshot date - the trend series."""
    s = snap.assign(par_bal=snap["outstanding_balance"].where(snap["days_in_arrears"] > 0, 0.0))
    g = s.groupby("extraction_date").agg(
        loans=("loan_no", "count"),
        outstanding=("outstanding_balance", "sum"),
        par_bal=("par_bal", "sum"),
        received=("total_amount_received", "sum"),
        scheduled=("total_scheduled_repayment", "sum"),
        interest_paid=("interest_paid", "sum"),
        interest_due=("interest_due", "sum"),
    )
    g["par"] = g["par_bal"] / g["outstanding"] * 100
    g["ce"] = g["received"] / g["scheduled"] * 100
    g["realization"] = g["interest_paid"] / g["interest_due"] * 100
    return g.reset_index()


def what_changed(snap: pd.DataFrame) -> dict | None:
    """Compare the latest snapshot with the previous one, for the currently filtered book."""
    dates = sorted(snap["extraction_date"].unique())
    if len(dates) < 2:
        return None
    cur = snap[snap["extraction_date"] == dates[-1]].set_index("loan_no")
    prev = snap[snap["extraction_date"] == dates[-2]].set_index("loan_no")
    new_ids = cur.index.difference(prev.index)
    exited_ids = prev.index.difference(cur.index)
    both = cur.index.intersection(prev.index)
    loss_now = cur["par_band"] == "Loss"
    newly_loss_ids = cur.index[loss_now & ~cur.index.isin(prev.index[prev["par_band"] == "Loss"])]
    cold_now = cur["flag_cold"].astype(bool)
    prev_cold_ids = prev.index[prev["flag_cold"].astype(bool)]
    newly_cold_ids = cur.index[cold_now & ~cur.index.isin(prev_cold_ids)]
    return {
        "prev_date": pd.Timestamp(dates[-2]),
        "new_loans": len(new_ids),
        "new_amount": float(cur.loc[new_ids, "approved_amount"].sum()),
        "exited": len(exited_ids),
        "exited_amount": float(prev.loc[exited_ids, "outstanding_balance"].sum()),
        "newly_loss": len(newly_loss_ids),
        "newly_loss_ids": set(newly_loss_ids),
        "newly_loss_amount": float(cur.loc[newly_loss_ids, "outstanding_balance"].sum()),
        "newly_cold": len(newly_cold_ids),
        "continuing": len(both),
    }


def add_flags(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Adds loan_age_days and early_default (Loss band within 60 days of disbursement)."""
    out = df.copy()
    out["loan_age_days"] = (as_of - out["disbursement_date"]).dt.days
    out["early_default"] = (out["par_band"] == "Loss") & (out["loan_age_days"] <= EARLY_DEFAULT_DAYS)
    return out


def hhi(share_pct: pd.Series) -> float:
    """Herfindahl-Hirschman index on the standard 0-10,000 scale."""
    return float(((share_pct / 100) ** 2).sum() * 10_000)


def hhi_label(v: float) -> str:
    return "low" if v < 1500 else ("moderate" if v < 2500 else "high")


def group_summary(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Loans, outstanding, PAR% and collection efficiency per group (vectorised)."""
    d = df.assign(par_bal=df["outstanding_balance"].where(df["days_in_arrears"] > 0, 0.0))
    g = d.groupby(by).agg(
        loans=("loan_no", "count"),
        outstanding=("outstanding_balance", "sum"),
        par_bal=("par_bal", "sum"),
        received=("total_amount_received", "sum"),
        scheduled=("total_scheduled_repayment", "sum"),
        interest_due=("interest_due", "sum"),
        interest_paid=("interest_paid", "sum"),
        approved=("approved_amount", "sum"),
    )
    g["par"] = g["par_bal"] / g["outstanding"] * 100
    g["ce"] = g["received"] / g["scheduled"] * 100
    g["share"] = g["outstanding"] / g["outstanding"].sum() * 100
    g["yield_expected"] = g["interest_due"] / g["approved"] * 100
    g["yield_realized"] = g["interest_paid"] / g["approved"] * 100
    return g
