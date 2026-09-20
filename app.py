"""
Loan portfolio control board - Streamlit dashboard.

Layout (top to bottom):
  1. Verdict row      - PAR% as the headline, one tile each for collections, book size and yield
  2. Trend + changes  - PAR trend across snapshots, and what changed since the previous snapshot
  3. Needs attention  - exceptions surfaced on the page, not buried in a tab
  4. Tabs             - Risk / Collections / Portfolio / Data & system, for depth

All data is SYNTHETIC. One sidebar filter set (branch, champion, product) feeds every panel.
"""
import pandas as pd
import streamlit as st

import config
from dashboard import charts, data, metrics as M

st.set_page_config(page_title="Loan portfolio control board", page_icon=":material/monitoring:",
                   layout="wide", initial_sidebar_state="expanded")

# ----------------------------------------------------------------------------- data + filters
cur_all = data.load_current()
snap_all = data.load_snapshot()
runlog = data.load_run_log()
as_of = cur_all["extraction_date"].max()


def _reset_filters():
    for key in ("f_branch", "f_champ", "f_product"):
        st.session_state[key] = []


with st.sidebar:
    st.header("Filters", anchor=False)
    branch = st.multiselect("Branch", sorted(cur_all["branch_code"].dropna().unique()), key="f_branch", placeholder="All branches")
    champ = st.multiselect("Collection champion", sorted(cur_all["collection_champ_name"].dropna().unique()), key="f_champ", placeholder="All champions")
    product = st.multiselect("Product", sorted(cur_all["loan_product_type_name"].dropna().unique()), key="f_product", placeholder="All products")
    st.button("Reset filters", icon=":material/restart_alt:", on_click=_reset_filters, width="stretch")
    st.divider()
    st.caption("Filters apply to every number, chart and table on the page.")

cur = data.apply_filters(cur_all, branch, champ, product)
snap = data.apply_filters(snap_all, branch, champ, product)

st.header("Loan portfolio control board", anchor=False)
with st.container(horizontal=True):
    st.badge(f"Snapshot {as_of:%d %b %Y}", icon=":material/calendar_today:", color="gray")
    st.badge("Synthetic data", icon=":material/science:", color="violet",
             help="Every record is generated. No real borrowers, lenders or transactions.")
    st.badge(f"{snap_all['extraction_date'].nunique()} snapshots of history", icon=":material/history:", color="gray")

if cur.empty:
    st.warning("No loans match the current filters. Adjust or reset them in the sidebar.")
    st.stop()

k = M.kpis(cur)
hist = M.history(snap)
prev = hist.iloc[-2] if len(hist) > 1 else None
cur_f = M.add_flags(cur, as_of)
chg = M.what_changed(snap)


def _delta_pp(now, before):
    return None if before is None else f"{now - before:+.1f} pp"


# ----------------------------------------------------------------------------- 1. verdict row
left, right = st.columns([2, 3], gap="medium")
with left:
    with st.container(border=True):
        st.caption("PORTFOLIO AT RISK (PAR)")
        st.title(f"{k['par']:.1f}%", anchor=False)
        label, colour = M.par_state(k["par"])
        with st.container(horizontal=True):
            st.badge(label, color=colour, icon=":material/monitor_heart:")
            if prev is not None:
                d = k["par"] - prev["par"]
                dcol = "gray" if abs(d) < 0.05 else ("red" if d > 0 else "green")
                st.badge(f"{d:+.1f} pp vs previous snapshot", color=dcol,
                         icon=":material/trending_up:" if d > 0 else ":material/trending_down:")
        st.caption(f"Share of outstanding principal on loans with any days in arrears. "
                   f"Illustrative bands: <{M.PAR_HEALTHY_BELOW:.0f}% healthy, {M.PAR_HEALTHY_BELOW:.0f}–{M.PAR_HIGH_ABOVE:.0f}% elevated, "
                   f">{M.PAR_HIGH_ABOVE:.0f}% high.")
with right:
    c1, c2, c3 = st.columns(3)
    spark = lambda col: hist[col].tolist() if len(hist) > 1 else None
    c1.metric("Collection efficiency", f"{k['ce']:.1f}%", delta=_delta_pp(k["ce"], None if prev is None else prev["ce"]),
              chart_data=spark("ce"), border=True,
              help="Total received ÷ total scheduled repayment over each loan's life. Because the schedule is lifetime, "
                   "it also reflects how far through their terms the loans are.")
    c2.metric("Outstanding principal (KES)", f"{k['outstanding']:,.0f}",
              delta=None if prev is None else f"{(k['outstanding'] / prev['outstanding'] - 1) * 100:+.1f}%",
              delta_color="off", chart_data=spark("outstanding"), border=True,
              help=f"{k['loans']:,} active loans in the current view.")
    c3.metric("Interest realization", f"{k['realization']:.1f}%", delta=_delta_pp(k["realization"], None if prev is None else prev["realization"]),
              chart_data=spark("realization"), border=True,
              help="Interest paid ÷ interest due (lifetime). The gap to 100% is scheduled interest not yet collected.")

# ----------------------------------------------------------------------------- 2. trend + what changed
tcol, wcol = st.columns([3, 2], gap="medium")
with tcol:
    with st.container(border=True):
        hc, pc = st.columns([2, 3])
        hc.markdown("**PAR trend**")
        period = pc.segmented_control("Period", ["7 days", "14 days", "All"], default="All", label_visibility="collapsed", key="period")
        window = {"7 days": 7, "14 days": 14}.get(period or "All")
        h = hist.tail(window) if window else hist
        st.altair_chart(charts.trend_line(h, "extraction_date", "par", "PAR %"), width="stretch")
        st.caption(f"{len(h)} snapshot(s) shown. Points are joined, not smoothed.")
with wcol:
    with st.container(border=True):
        if chg is None:
            st.markdown("**What changed**")
            st.info("Only one snapshot in the current view, so there is nothing to compare yet.")
        else:
            st.markdown(f"**What changed since {chg['prev_date']:%d %b}**")
            a, b = st.columns(2)
            a.metric("New loans", f"{chg['new_loans']:,}", help=f"KES {chg['new_amount']:,.0f} approved.")
            b.metric("Loans closed or written off", f"{chg['exited']:,}", help=f"KES {chg['exited_amount']:,.0f} of principal left the book (completed or removed from the active file).")
            a, b = st.columns(2)
            a.metric("Newly in Loss", f"{chg['newly_loss']:,}", help=f"KES {chg['newly_loss_amount']:,.0f} outstanding. Loans that were not in the Loss band at the previous snapshot.")
            b.metric("Newly cold", f"{chg['newly_cold']:,}", help=f"No payment for more than {config.COLD_THRESHOLD_DAYS} days, and not cold at the previous snapshot.")

# ----------------------------------------------------------------------------- 3. needs attention
st.subheader("Needs attention", anchor=False)
cur_f["newly_loss"] = cur_f["loan_no"].isin(chg["newly_loss_ids"]) if chg else False
FLAGS = {"flag_escalate": f"No payment >{config.ESCALATE_THRESHOLD_DAYS}d", "early_default": "Early default", "newly_loss": "Newly in Loss"}
mask = cur_f[list(FLAGS)].any(axis=1)
exc = cur_f[mask].copy()
if exc.empty:
    st.success("No loans are flagged in the current view.", icon=":material/check_circle:")
else:
    exc["Flags"] = exc.apply(lambda r: " · ".join(lbl for col, lbl in FLAGS.items() if r[col]), axis=1)
    exc = exc.sort_values("outstanding_balance", ascending=False)
    with st.container(horizontal=True):
        for col, lbl in FLAGS.items():
            n = int(cur_f[col].sum())
            st.badge(f"{n} · {lbl}", color="red" if n else "gray")
        st.caption(f"{len(exc)} loan(s) flagged, largest balance first")
    view = exc[["loan_no", "member_name", "collection_champ_name", "branch_code", "outstanding_balance",
                "days_in_arrears", "days_since_last_pay", "Flags"]].copy()
    view["outstanding_balance"] = view["outstanding_balance"].round().astype(int)
    st.dataframe(view, hide_index=True, height=min(60 + 35 * len(view), 380), column_config={
        "loan_no": "Loan", "member_name": "Member", "collection_champ_name": "Champion", "branch_code": "Branch",
        "outstanding_balance": st.column_config.NumberColumn("Balance (KES)", format="%,d"),
        "days_in_arrears": st.column_config.NumberColumn("Days in arrears", format="%d"),
        "days_since_last_pay": st.column_config.NumberColumn("Days since payment", format="%d"),
    })

st.divider()

# ----------------------------------------------------------------------------- 4. tabs
tab_risk, tab_coll, tab_port, tab_sys = st.tabs(["Risk", "Collections", "Portfolio", "Data & system"])

# ============================== RISK
with tab_risk:
    st.subheader("PAR banding", anchor=False)
    st.caption("Bands follow the source system's days-in-arrears categories: 0 = Performing, 1 = Watch, 2 = Substandard, 3 = Doubtful, 4+ = Loss.")
    band = cur.groupby("par_band").agg(loans=("loan_no", "count"), balance=("outstanding_balance", "sum")).reindex(M.PAR_BANDS).fillna(0)
    band["share"] = band["balance"] / band["balance"].sum() * 100
    bc, bt = st.columns([3, 2])
    bc.altair_chart(charts.par_band_bar(band), width="stretch")
    bt.dataframe(band.assign(balance=band["balance"].round().astype(int)), column_config={
        "par_band": "Band", "loans": st.column_config.NumberColumn("Loans", format="%,d"),
        "balance": st.column_config.NumberColumn("Outstanding (KES)", format="%,d"),
        "share": st.column_config.NumberColumn("% of book", format="%.1f%%")}, height=245)

    st.divider()
    lc, wc = st.columns(2, gap="large")
    with lc:
        st.subheader("Loss severity", anchor=False)
        st.caption("Loans in the Loss band, split by how long they have been in arrears. A 10-day-old Loss loan and a 300-day-old one need very different handling.")
        loss = cur[cur["par_band"] == "Loss"]
        if loss.empty:
            st.info("No loans in the Loss band in this view.")
        else:
            sev = loss.groupby("loss_severity").agg(loans=("loan_no", "count"), balance=("outstanding_balance", "sum")).reindex(M.LOSS_SEVERITY).fillna(0)
            st.altair_chart(charts.loss_severity_bar(sev), width="stretch")
    with wc:
        st.subheader("Watch despite good standing", anchor=False)
        st.caption("Zero days late today, but the loan's historical average arrears (PAR AVG) is above this snapshot's 75th percentile: current, with a rocky record.")
        wd = cur[cur["watch_despite_good_standing"]]
        m1, m2 = st.columns(2)
        m1.metric("Loans flagged", f"{len(wd):,}")
        m2.metric("Balance (KES)", f"{wd['outstanding_balance'].sum():,.0f}")
        if not wd.empty:
            t = wd.sort_values("par_avg", ascending=False).head(10)[["member_name", "branch_code", "collection_champ_name", "par_avg", "outstanding_balance"]].copy()
            t["outstanding_balance"] = t["outstanding_balance"].round().astype(int)
            st.dataframe(t, hide_index=True, column_config={
                "member_name": "Member", "branch_code": "Branch", "collection_champ_name": "Champion",
                "par_avg": st.column_config.NumberColumn("PAR AVG (days)", format="%.2f"),
                "outstanding_balance": st.column_config.NumberColumn("Balance (KES)", format="%,d")})

    st.divider()
    cc, pc2 = st.columns(2, gap="large")
    with cc:
        st.subheader("Collateral and recovery", anchor=False)
        under = cur[cur["collateral_coverage"] < 1.0]
        repo = cur[cur["repo_fee_count"] > 0]
        m1, m2 = st.columns(2)
        m1.metric("Under-collateralized", f"{len(under):,}", help="Security amount is below the approved amount (coverage < 1.0×).")
        m2.metric("Repossession events", f"{len(repo):,}", help="Loans with at least one repossession fee recorded.")
        st.altair_chart(charts.hist(cur[["collateral_coverage"]].clip(upper=8), "collateral_coverage",
                                    "Collateral coverage (security ÷ approved, capped at 8×)", rules=[(1.0, "1.0×", charts.MUTED)]), width="stretch")
    with pc2:
        st.subheader("Plan deviation", anchor=False)
        st.caption(f"Actual net balance minus the scheduled net balance. Flagged when above KES {config.PLAN_DEVIATION_MATERIALITY_KES:,.0f}. "
                   "That threshold is a placeholder, not statistically derived, so treat the count as directional.")
        mat = cur[cur["plan_deviation_material_flag"]]
        m1, m2 = st.columns(2)
        m1.metric("Loans behind plan", f"{len(mat):,}", f"{len(mat) / len(cur) * 100:.1f}% of view", delta_color="off")
        m2.metric("Total deviation (KES)", f"{mat['plan_deviation'].sum():,.0f}")
        t = mat.sort_values("plan_deviation", ascending=False).head(8)[["loan_no", "collection_champ_name", "plan_deviation"]].copy()
        t["plan_deviation"] = t["plan_deviation"].round().astype(int)
        st.dataframe(t, hide_index=True, column_config={"loan_no": "Loan", "collection_champ_name": "Champion",
                     "plan_deviation": st.column_config.NumberColumn("Deviation (KES)", format="%,d")})

    st.divider()
    st.subheader("Early defaults", anchor=False)
    st.caption(f"A loan in the Loss band within {M.EARLY_DEFAULT_DAYS} days of disbursement. This points at approval and vetting quality at origination, not collections effort.")
    ed = cur_f[cur_f["early_default"]]
    e1, e2, e3 = st.columns(3)
    e1.metric("Early-default loans", f"{len(ed):,}")
    e2.metric("% of view", f"{len(ed) / len(cur_f) * 100:.1f}%")
    e3.metric("Balance (KES)", f"{ed['outstanding_balance'].sum():,.0f}")
    if not ed.empty:
        byc = ed.groupby("collection_champ_name").agg(loans=("loan_no", "count")).reset_index().sort_values("loans", ascending=False).head(10)
        st.altair_chart(charts.hbar(byc, "collection_champ_name", "loans", "Early-default loans", fmt=",d"), width="stretch")

    st.divider()
    st.subheader("Concentration", anchor=False)
    st.caption("HHI is on the standard 0–10,000 scale: below ~1,500 low, 1,500–2,500 moderate, above 2,500 high. It is a diagnostic, not a verdict on what is too concentrated.")
    gc = M.group_summary(cur, "collection_champ_name")
    gb = M.group_summary(cur, "branch_code")
    top10 = cur.nlargest(10, "outstanding_balance")["outstanding_balance"].sum() / cur["outstanding_balance"].sum() * 100
    h1, h2, h3 = st.columns(3)
    hc_, hb_ = M.hhi(gc["share"]), M.hhi(gb["share"])
    h1.metric("Champion HHI", f"{hc_:,.0f}", f"{M.hhi_label(hc_)} · top 3 hold {gc['share'].nlargest(3).sum():.1f}%", delta_color="off")
    h2.metric("Branch HHI", f"{hb_:,.0f}", f"{M.hhi_label(hb_)} · top 3 hold {gb['share'].nlargest(3).sum():.1f}%", delta_color="off")
    h3.metric("Top 10 loans", f"{top10:.1f}%", "of outstanding principal", delta_color="off")
    top = gc["share"].nlargest(8).reset_index().rename(columns={"share": "Share"})
    st.altair_chart(charts.hbar(top, "collection_champ_name", "Share", "% of outstanding principal"), width="stretch")

# ============================== COLLECTIONS
with tab_coll:
    st.subheader("Collection efficiency", anchor=False)
    st.caption("Total received ÷ total scheduled repayment, over each loan's whole schedule. Read it as share of the schedule collected so far; loans early in their term naturally score lower.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall collection efficiency", f"{k['ce']:.1f}%")
    cold = cur[cur["flag_cold"]]
    esc = cur[cur["flag_escalate"]]
    c2.metric(f"Cold (>{config.COLD_THRESHOLD_DAYS} days since payment)", f"{len(cold):,}")
    c3.metric(f"Escalate (>{config.ESCALATE_THRESHOLD_DAYS} days)", f"{len(esc):,}", help="A subset of the cold loans.")
    ec, dc = st.columns(2, gap="large")
    ec.altair_chart(charts.hist(cur[["collection_efficiency_pct"]].dropna(), "collection_efficiency_pct", "Collection efficiency % (per loan)", extent=(0, 100)), width="stretch")
    dc.altair_chart(charts.hist(cur[["days_since_last_pay"]].clip(upper=60), "days_since_last_pay", "Days since last payment (capped at 60)",
                                rules=[(config.COLD_THRESHOLD_DAYS, "cold", "#D9A63E"), (config.ESCALATE_THRESHOLD_DAYS, "escalate", charts.LOSS_RED)]), width="stretch")

    st.divider()
    st.subheader("Follow-up lists", anchor=False)
    lc, rc = st.columns(2, gap="large")
    cols = ["member_name", "branch_code", "collection_champ_name", "days_since_last_pay", "outstanding_balance"]
    cfg = {"member_name": "Member", "branch_code": "Branch", "collection_champ_name": "Champion",
           "days_since_last_pay": st.column_config.NumberColumn("Days since payment", format="%d"),
           "outstanding_balance": st.column_config.NumberColumn("Balance (KES)", format="%,d")}
    for holder, title, frame in ((lc, f"Cold: {config.COLD_THRESHOLD_DAYS + 1}–{config.ESCALATE_THRESHOLD_DAYS} days", cur[cur["flag_cold"] & ~cur["flag_escalate"]]),
                                 (rc, f"Escalate: over {config.ESCALATE_THRESHOLD_DAYS} days", esc)):
        with holder:
            st.markdown(f"**{title}** · {len(frame):,} loan(s)")
            if frame.empty:
                st.caption("None in this view.")
            else:
                t = frame.sort_values("days_since_last_pay", ascending=False)[cols].copy()
                t["outstanding_balance"] = t["outstanding_balance"].round().astype(int)
                st.dataframe(t, hide_index=True, height=300, column_config=cfg)

    st.divider()
    st.subheader("Champion leaderboard", anchor=False)
    st.caption("Efficiency and risk read together: a champion can look efficient while carrying a high-PAR book. Bubble size is outstanding principal.")
    lb = gc.copy()
    st.altair_chart(charts.champion_scatter(lb), width="stretch")
    t = lb.sort_values("outstanding", ascending=False)[["loans", "outstanding", "ce", "par"]].copy()
    t["outstanding"] = t["outstanding"].round().astype(int)
    st.dataframe(t, column_config={
        "collection_champ_name": "Champion", "loans": st.column_config.NumberColumn("Loans", format="%,d"),
        "outstanding": st.column_config.NumberColumn("Outstanding (KES)", format="%,d"),
        "ce": st.column_config.ProgressColumn("Collection efficiency", format="%.1f%%", min_value=0, max_value=100),
        "par": st.column_config.NumberColumn("PAR %", format="%.1f%%")})

# ============================== PORTFOLIO
with tab_port:
    st.subheader("Exposure and composition", anchor=False)
    bcol, pcol = st.columns(2, gap="large")
    with bcol:
        st.markdown("**Outstanding principal by branch**")
        gb2 = gb.sort_values("outstanding", ascending=False).reset_index()
        st.altair_chart(charts.hbar(gb2, "branch_code", "outstanding", "Outstanding principal (KES)", fmt=",.0f"), width="stretch")
        t = gb2[["branch_code", "loans", "share", "par"]]
        st.dataframe(t, hide_index=True, column_config={
            "branch_code": "Branch", "loans": st.column_config.NumberColumn("Loans", format="%,d"),
            "share": st.column_config.NumberColumn("% of book", format="%.1f%%"), "par": st.column_config.NumberColumn("PAR %", format="%.1f%%")})
    with pcol:
        st.markdown("**Portfolio mix by product**")
        gp = M.group_summary(cur, "loan_product_type_name")
        gp2 = gp.sort_values("outstanding", ascending=False).reset_index()
        st.altair_chart(charts.hbar(gp2, "loan_product_type_name", "share", "% of outstanding principal"), width="stretch")
        t = gp2[["loan_product_type_name", "loans", "share", "par"]]
        st.dataframe(t, hide_index=True, column_config={
            "loan_product_type_name": "Product", "loans": st.column_config.NumberColumn("Loans", format="%,d"),
            "share": st.column_config.NumberColumn("% of book", format="%.1f%%"), "par": st.column_config.NumberColumn("PAR %", format="%.1f%%")})

    st.divider()
    st.subheader("Yield", anchor=False)
    st.caption("Expected yield is scheduled interest ÷ approved amount. Realized yield is interest actually paid ÷ approved amount. Both are lifetime figures for loans still on the book.")
    y1, y2, y3 = st.columns(3)
    y1.metric("Expected yield", f"{k['yield_expected']:.1f}%")
    y2.metric("Realized yield", f"{k['yield_realized']:.1f}%")
    y3.metric("Realization rate", f"{k['realization']:.1f}%", help="Interest paid ÷ interest due. Interest income at risk is separate from PAR, which only covers principal.")
    st.altair_chart(charts.grouped_yield(gp), width="stretch")

    st.divider()
    st.subheader("Book over time", anchor=False)
    oc, lc2 = st.columns(2, gap="large")
    oc.altair_chart(charts.book_over_time(hist), width="stretch")
    lc2.altair_chart(charts.trend_line(hist, "extraction_date", "loans", "Active loans", fmt=",d"), width="stretch")
    st.caption(f"{len(hist)} snapshot(s). Both lines reflect the current filters.")

    st.divider()
    st.subheader("Vintage (cohort) view", anchor=False)
    st.warning("Current-snapshot view only. Older cohorts are survivorship-biased: loans that finished well have already left the active file, "
               "so old cohorts still here are disproportionately the problem loans. Judge underwriting quality from the recent, thicker cohorts.", icon=":material/warning:")
    v = cur.assign(disb_month=cur["disbursement_date"].dt.to_period("M").astype(str),
                   par_bal=cur["outstanding_balance"].where(cur["days_in_arrears"] > 0, 0.0))
    vg = v.groupby("disb_month").agg(loans=("loan_no", "count"), bal=("outstanding_balance", "sum"), par_bal=("par_bal", "sum"))
    vg["par"] = vg["par_bal"] / vg["bal"] * 100
    recent_only = st.toggle("Show only the last 12 cohorts", value=True)
    st.altair_chart(charts.vintage(vg.tail(12) if recent_only else vg), width="stretch")

# ============================== DATA & SYSTEM
with tab_sys:
    st.subheader("About this project", anchor=False)
    st.markdown(
        "A portfolio-monitoring dashboard for a small-ticket, daily-repayment credit lender. "
        "**All data is synthetic**: a generator simulates borrowers, repayments, arrears and write-offs, writes daily raw exports, "
        "and those run through the same ETL that would process a real system export. The parameters are illustrative and are "
        "not calibrated to any real institution.")
    st.divider()
    st.subheader("Pipeline status", anchor=False)
    ok = runlog[runlog["status"] == "success"]
    anchor_ts = runlog["started_at"].max()
    recent_fail = runlog[(runlog["status"] == "failed") & (runlog["started_at"] >= anchor_ts - pd.Timedelta(days=30))]
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Last successful load", f"{ok['extraction_date'].max():%d %b %Y}")
    s2.metric("Rows in last load", f"{int(ok.sort_values('finished_at').iloc[-1]['rows_loaded']):,}")
    s3.metric("Successful runs", f"{len(ok):,}")
    s4.metric("Failed runs, last 30 days", f"{len(recent_fail):,}", help="Counted back from the most recent run, since this is a static demo dataset.")
    st.caption("The run log is simulated: nightly timestamps plus two failed-then-retried runs.")
    log = runlog.copy()
    st.dataframe(log.style.map(lambda v: "color: #D9534F" if v == "failed" else "color: #4C9A6A", subset=["status"]),
                 hide_index=True, height=300, column_config={
                     "run_id": "Run", "started_at": st.column_config.DatetimeColumn("Started", format="DD MMM YYYY, HH:mm"),
                     "finished_at": st.column_config.DatetimeColumn("Finished", format="DD MMM YYYY, HH:mm"),
                     "source_filename": "Source file", "extraction_date": st.column_config.DateColumn("Extraction date", format="DD MMM YYYY"),
                     "rows_loaded": st.column_config.NumberColumn("Rows", format="%,d"), "status": "Status", "error_message": "Error"})

    st.divider()
    st.subheader("Assumptions in force", anchor=False)
    st.dataframe(pd.DataFrame([
        ("Cold flag", f"> {config.COLD_THRESHOLD_DAYS} days since last payment", "config.py (COLD_THRESHOLD_DAYS)"),
        ("Escalate flag", f"> {config.ESCALATE_THRESHOLD_DAYS} days since last payment", "config.py (ESCALATE_THRESHOLD_DAYS)"),
        ("Plan-deviation materiality", f"> KES {config.PLAN_DEVIATION_MATERIALITY_KES:,.0f}", "config.py (placeholder, not statistically derived)"),
        ("Early default", f"Loss band within {M.EARLY_DEFAULT_DAYS} days of disbursement", "dashboard/metrics.py"),
        ("Headline PAR bands", f"<{M.PAR_HEALTHY_BELOW:.0f}% healthy · {M.PAR_HEALTHY_BELOW:.0f}–{M.PAR_HIGH_ABOVE:.0f}% elevated · >{M.PAR_HIGH_ABOVE:.0f}% high", "dashboard/metrics.py (illustrative)"),
        ("Watch despite good standing", "0 days late and PAR AVG above the snapshot's 75th percentile", "etl.py"),
        ("HHI reading", "<1,500 low · 1,500–2,500 moderate · >2,500 high", "standard scale"),
    ], columns=["Assumption", "Value", "Where it lives"]), hide_index=True)
