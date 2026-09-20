"""
Synthetic loan-book generator.

Produces one raw export per day in the SAME 80-column layout (names, order,
text formats, quirks) that the ETL in `etl.py` expects, so the pipeline, schema
and engineered metrics run on it completely unchanged.

Design:
  * Loans are simulated independently, day by day, from disbursement onward:
    each day a borrower may pay that day's instalment and (if behind) catch up.
    "Days in arrears" = instalments due minus instalments paid.
  * Three borrower types - good / shaky / defaulter - with the default rate
    scaled by product risk and a per-champion multiplier, so champions differ.
  * Defaulted loans linger in the file for a while (like a real book) before
    being written off; completed loans leave the file.
  * Every identifier is fabricated: members, champions, team leads and stages
    are coded pseudonyms ("Member M-01234", "Champion 07").

Run:  python -m synthetic.generate --out raw
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from synthetic import params as P

# Exact raw column order of the source export (first column carries a BOM in the real file;
# we write utf-8-sig so it is reproduced).
RAW_COLUMNS = [
    "Member No.", "Member Name", "Phone Number", "Car Registration Number", "Stage Name",
    "Amount in Arrears", "Net Balance", "Repayment", "Days in Arrears", "Application Date",
    "Disbursement Date", "Repayment Start Date", "Expected Date of Completion",
    "Collection Champ Name", "Collection Troops", "Collection Troops Name", "Interest Repayment",
    "PAR AVG", "Branch Code", "ID No.", "Loan No.", "Approved Amount", "Requested Amount",
    "Collection Champion", "Performance Category", "Penalty Amount", "Savings Balance",
    "Asset Type", "Motor Bike Type", "Pin Number", "Savings Accounts", "Security Amount",
    "Interest Due Date", "Interest Posting Date", "Next Run Date", "Last Pay Date",
    "Penalty Posting Date", "Loan Product Type", "Loan Product Type Name", "Installments",
    "Interest", "Current Scheduled Interest", "PAR Historical Information", "Interest Paid",
    "Interest Due", "Principle Repayment", "Principal Paid", "Loan Account",
    "Loan Repayment Account", "Disbursement Account No", "Stage Code", "Repayment Status",
    "Interest Calculation Method", "Batch No.", "ToBe Modified", "Outstanding Balance",
    "Outstanding Interest", "Outstanding Penalty", "Repo Fee Due", "Repair Fee Balance",
    "Re-Po Fee Count", "Repo Fee Balance", "Tracking Fee Repair Balance",
    "Outstanding Processing Fee", "Tracking Fee Balance", "Total Outstanding Balance",
    "Total Amount Received", "Total Scheduled Repayment", "Excess Amount Paid", "Savingbalance",
    "Schedule Principal Repayments", "Scheduled Interest", "Total Interest Paid",
    "Total Interest Charged", "Schedule Interest Paid", "Schedule Interest Balance",
    "Excess Interest Charged", "Excess Interest Paid", "Excess Interest Balance",
    "Schedule Net Balance",
]
assert len(RAW_COLUMNS) == 80

# The source system's own (misspelled) label for the 0-days band is reproduced on purpose;
# the ETL derives its own clean `par_band` separately.
PERF_LABELS = ["Perfoming", "Watch", "Substandard", "Doubtful"]  # 0,1,2,3 ; >=4 -> Loss


def _perf(d: int) -> str:
    return PERF_LABELS[d] if d < 4 else "Loss"


def _money(x: float) -> str:
    return f"{x:,.2f}"


def _mdy(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


# --------------------------------------------------------------------------------------
# Organisation
# --------------------------------------------------------------------------------------
def build_org(rng: np.random.Generator) -> dict:
    champs = []
    weights = rng.lognormal(0, P.CHAMPION_BOOK_SIGMA, P.N_CHAMPIONS)
    weights /= weights.sum()
    for i in range(1, P.N_CHAMPIONS + 1):
        team = (i - 1) % P.N_TEAMS + 1
        champs.append({
            "code": f"COL/{i:03d}",
            "name": f"Champion {i:02d}",
            "team_code": f"TRP/{team:03d}",
            "team_lead": f"Team Lead {team}",
            "home_branch": str(rng.choice(P.BRANCHES)),
            "quality_mult": float(rng.lognormal(0, P.CHAMPION_QUALITY_SIGMA)),
            "weight": float(weights[i - 1]),
        })
    return {"champions": champs}


# --------------------------------------------------------------------------------------
# Loan simulation
# --------------------------------------------------------------------------------------
def simulate_loans(rng: np.random.Generator, org: dict, first_snap: date, end: date) -> list[dict]:
    start = first_snap - timedelta(days=P.BURN_IN_DAYS)
    total_days = (end - start).days
    champs = org["champions"]
    champ_w = np.array([c["weight"] for c in champs])
    prod_w = np.array([p[2] for p in P.PRODUCTS]); prod_w = prod_w / prod_w.sum()
    asset_names = [a[0] for a in P.ASSET_TYPES]
    asset_w = np.array([a[1] for a in P.ASSET_TYPES]); asset_w = asset_w / asset_w.sum()

    members: dict[int, dict] = {}
    member_ids: list[int] = []
    next_member = 1000
    loans: list[dict] = []
    seq = 3000

    for day_idx in range(total_days + 1):
        d0 = start + timedelta(days=day_idx)
        frac = day_idx / max(total_days, 1)
        lam = P.DAILY_ORIGINATIONS_START + (P.DAILY_ORIGINATIONS_END - P.DAILY_ORIGINATIONS_START) * frac
        if d0.weekday() == 6:
            lam *= P.SUNDAY_FACTOR
        for _ in range(rng.poisson(lam)):
            # borrower
            if member_ids and rng.random() < P.REPEAT_BORROWER_SHARE:
                mno = int(rng.choice(member_ids))
            else:
                next_member += int(rng.integers(1, 6))
                mno = next_member
                member_ids.append(mno)
                members[mno] = {"stage_code": int(rng.integers(1, 160)),
                                "savings": 0 if rng.random() < 0.55 else int(rng.lognormal(np.log(400), 0.9))}
            m = members[mno]

            # product / terms
            pi = int(rng.choice(len(P.PRODUCTS), p=prod_w))
            code, pname, _, med, rate, term_w, prisk = P.PRODUCTS[pi]
            tw = np.array(term_w, dtype=float); tw /= tw.sum()
            n = int(P.TERMS[int(rng.choice(len(P.TERMS), p=tw))])
            amount = int(np.clip(round(rng.lognormal(np.log(med), P.AMOUNT_SIGMA), -2), P.AMOUNT_MIN, P.AMOUNT_MAX))
            interest = int(round(amount * rate * n))
            fee = int(round(P.TRACKING_FEE_PER_DAY * n))
            total = amount + interest + fee
            inst = int(round(total / n))

            # champion / branch
            ch = champs[int(rng.choice(len(champs), p=champ_w))]
            branch = ch["home_branch"] if rng.random() < P.CHAMPION_HOME_BRANCH_SHARE else str(rng.choice(P.BRANCHES))

            # behaviour
            p_def = float(np.clip(P.P_DEFAULTER_BASE * prisk * ch["quality_mult"], 0.01, 0.40))
            p_shk = float(np.clip(P.P_SHAKY_BASE * prisk, 0.0, 0.40))
            u = rng.random()
            kind = "defaulter" if u < p_def else ("shaky" if u < p_def + p_shk else "good")

            stop = writeoff = None
            if kind == "defaulter":
                stop = max(2, int(n * rng.uniform(*P.DEFAULT_STOP_FRACTION)))
                writeoff = stop + max(30, int(rng.exponential(P.WRITE_OFF_MEAN_DAYS)))

            S = (end - d0).days
            u1 = rng.random(max(S, 1)); u2 = rng.random(max(S, 1))
            ks = np.zeros(S + 1, dtype=np.int32)
            lps = np.zeros(S + 1, dtype=np.int32)
            cds = np.zeros(S + 1, dtype=np.float64)
            k = lp = 0; cum = 0.0
            alive_until = S + 1  # first offset at which the loan is NOT in the file
            for s in range(1, S + 1):
                key = "defaulter_after_stop" if (kind == "defaulter" and s >= stop) else ("shaky" if kind == "shaky" else "good")
                pp, pc = P.DAILY_PAY_PROB[key], P.DAILY_CATCHUP_PROB[key]
                if k < s and u1[s - 1] < pp:
                    k += 1; lp = s
                if k < s and k < n and u2[s - 1] < pc:
                    k += 1; lp = s
                cum += s - k
                ks[s] = k; lps[s] = lp; cds[s] = cum
                if k >= n or (writeoff is not None and s >= writeoff):
                    alive_until = s
                    break

            # repossession events (only meaningful for loans that get badly behind)
            dd = np.arange(S + 1) - ks
            repo1 = repo2 = 10**9
            hits = np.where(dd >= 25)[0]
            if len(hits) and rng.random() < P.REPO_PROB_FIRST:
                repo1 = int(hits[0]) + int(rng.integers(0, 10))
                if rng.random() < P.REPO_PROB_SECOND:
                    repo2 = repo1 + int(rng.integers(45, 90))

            seq += 1
            loans.append({
                "d0": d0, "n": n, "P": amount, "I": interest, "F": fee, "total": total, "inst": inst,
                "rate": rate, "pcode": code, "pname": pname,
                "member": mno, "stage_code": m["stage_code"], "savings": m["savings"],
                "champ": ch, "branch": branch,
                "loan_no": f"LN/{d0.year % 100:02d}/{seq:05d}",
                "security": int(round(amount * max(P.COLLATERAL_FLOOR, rng.lognormal(P.COLLATERAL_MU, P.COLLATERAL_SIGMA)))),
                "asset": str(rng.choice(asset_names, p=asset_w)),
                "int_repay": int(rng.choice([65, 91, 182])),
                "ks": ks, "lps": lps, "cds": cds, "alive_until": alive_until,
                "repo1": repo1, "repo2": repo2,
            })
    return loans


# --------------------------------------------------------------------------------------
# Row construction (one loan, one snapshot date)
# --------------------------------------------------------------------------------------
_BIKE_MODEL = {"Motorbike": ["Standard 125cc", "Standard 150cc", "Sport 200cc"],
               "Vehicle": ["Light vehicle"], "Equipment": ["Equipment"]}


def make_row(L: dict, s: int, t: date, rng_local: np.random.Generator) -> dict:
    n, inst, total = L["n"], L["inst"], L["total"]
    Pp, I, F = L["P"], L["I"], L["F"]
    k = int(L["ks"][s]); d = s - k
    received = min(k * inst, total)
    f = received / total
    prin_paid, int_paid, fee_paid = round(f * Pp), round(f * I), round(f * F)
    ob, oi, tfb = Pp - prin_paid, I - int_paid, F - fee_paid
    arrears_amt = min(d * inst, total - received)
    penalty = min(round(P.PENALTY_RATE_PER_ARREARS_DAY * inst * max(d - 1, 0)), 0.3 * Pp)
    repo_n = int(s >= L["repo1"]) + int(s >= L["repo2"])
    repo_bal = P.REPO_FEE * repo_n
    total_out = ob + oi + tfb + penalty + repo_bal
    sav = L["savings"]
    net = max(total_out - sav, 0)
    planned_received = min(s * inst, total)
    sched_net = max(total - planned_received - sav, 0)
    par_avg = round(float(L["cds"][s]) / s, 2) if s > 0 else 0.0
    lp = L["d0"] + timedelta(days=int(L["lps"][s])) if L["lps"][s] > 0 else L["d0"]
    mno, d0 = L["member"], L["d0"]
    ch = L["champ"]
    asset = L["asset"]
    model = _BIKE_MODEL[asset][mno % len(_BIKE_MODEL[asset])]

    return {
        "Member No.": mno,
        "Member Name": f"Member M-{mno:05d}",
        "Phone Number": f"0000{(mno * 7919) % 1_000_000:06d}",
        "Car Registration Number": f"XXX {mno % 1000:03d}{chr(65 + mno % 26)}",
        "Stage Name": f"Stage {L['stage_code']:03d}",
        "Amount in Arrears": _money(arrears_amt),
        "Net Balance": _money(net),
        "Repayment": _money(inst),
        "Days in Arrears": float(d),
        "Application Date": _mdy(d0 - timedelta(days=1)),
        "Disbursement Date": _mdy(d0),
        "Repayment Start Date": _mdy(d0 + timedelta(days=1)),
        "Expected Date of Completion": _mdy(d0 + timedelta(days=n)),
        "Collection Champ Name": ch["name"],
        "Collection Troops": ch["team_code"],
        "Collection Troops Name": ch["team_lead"],
        "Interest Repayment": float(L["int_repay"]),
        "PAR AVG": par_avg,
        "Branch Code": L["branch"],
        "ID No.": f"99{(mno * 104729) % 1_000_000:06d}",
        "Loan No.": L["loan_no"],
        "Approved Amount": _money(Pp),
        "Requested Amount": _money(Pp),
        "Collection Champion": ch["code"],
        "Performance Category": _perf(d),
        "Penalty Amount": float(penalty),
        "Savings Balance": _money(sav),
        "Asset Type": asset,
        "Motor Bike Type": model,
        "Pin Number": None,
        "Savings Accounts": _money(sav),
        "Security Amount": _money(L["security"]),
        "Interest Due Date": _mdy(d0 + timedelta(days=1)),
        "Interest Posting Date": _mdy(d0 + timedelta(days=1)),
        "Next Run Date": _mdy(d0 + timedelta(days=30)),
        "Last Pay Date": _mdy(lp),
        "Penalty Posting Date": _mdy(d0 + timedelta(days=8)),
        "Loan Product Type": L["pcode"],
        "Loan Product Type Name": L["pname"],
        "Installments": n,
        "Interest": round(L["rate"], 6),
        "Current Scheduled Interest": _money(I),
        "PAR Historical Information": 0,
        "Interest Paid": _money(int_paid),
        "Interest Due": _money(I),
        "Principle Repayment": _money(round(Pp / n)),
        "Principal Paid": _money(prin_paid),
        "Loan Account": mno,
        "Loan Repayment Account": None,
        "Disbursement Account No": "BNK001",
        "Stage Code": L["stage_code"],
        "Repayment Status": None,
        "Interest Calculation Method": "Straight Line",
        "Batch No.": None,
        "ToBe Modified": False,
        "Outstanding Balance": _money(ob),
        "Outstanding Interest": _money(oi),
        "Outstanding Penalty": float(penalty),
        "Repo Fee Due": _money(repo_bal),
        "Repair Fee Balance": 0.0,
        "Re-Po Fee Count": repo_n,
        "Repo Fee Balance": _money(repo_bal),
        "Tracking Fee Repair Balance": _money(0),
        "Outstanding Processing Fee": 0.0,
        "Tracking Fee Balance": _money(tfb),
        "Total Outstanding Balance": _money(total_out),
        "Total Amount Received": _money(received),
        "Total Scheduled Repayment": _money(total),
        "Excess Amount Paid": _money(0),
        "Savingbalance": _money(sav),
        "Schedule Principal Repayments": _money(Pp),
        "Scheduled Interest": _money(I),
        "Total Interest Paid": _money(int_paid),
        "Total Interest Charged": _money(I),
        "Schedule Interest Paid": _money(int_paid),
        "Schedule Interest Balance": _money(oi),
        "Excess Interest Charged": _money(0),
        "Excess Interest Paid": _money(0),
        "Excess Interest Balance": _money(0),
        "Schedule Net Balance": _money(sched_net),
    }


def generate(out_dir: str | Path = "raw") -> list[Path]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(P.SEED)
    snap_dates = [P.END_DATE - timedelta(days=i) for i in range(P.N_SNAPSHOTS - 1, -1, -1)]
    org = build_org(rng)
    loans = simulate_loans(rng, org, snap_dates[0], P.END_DATE)
    print(f"simulated {len(loans):,} loans over {P.BURN_IN_DAYS + P.N_SNAPSHOTS} days")

    paths = []
    for t in snap_dates:
        rows = []
        for L in loans:
            s = (t - L["d0"]).days
            if 0 <= s < L["alive_until"]:
                rows.append(make_row(L, s, t, rng))
        df = pd.DataFrame(rows, columns=RAW_COLUMNS)
        df = df.sort_values("Loan No.", ascending=False)
        path = out / f"loans_export_{t.isoformat()}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        paths.append(path)
    print(f"wrote {len(paths)} exports to {out}/  (last one: {len(rows):,} active loans)")
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="raw")
    generate(ap.parse_args().out)
