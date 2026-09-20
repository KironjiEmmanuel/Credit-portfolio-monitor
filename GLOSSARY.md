# Glossary

Every number, flag and chart in the dashboard, what it means, and how it is computed.
All data is synthetic. Currency is Kenya shillings (KES) throughout.

## 1. Page anatomy

| Section | Purpose |
|---|---|
| **Sidebar filters** | Branch, collection champion, product. One filter set feeds every panel, so no two panels can disagree about "the current view". |
| **Header badges** | Snapshot date shown, "Synthetic data" notice, number of daily snapshots held. |
| **Verdict row** | The one number to look at first (PAR%), plus one tile each for collections, book size and yield. |
| **PAR trend** | PAR% across snapshots, with a period toggle (7 days / 14 days / All). |
| **What changed** | Latest snapshot compared with the previous one. |
| **Needs attention** | Loans that trip an exception flag, largest balance first. |
| **Tabs** | Risk, Collections, Portfolio, Data & system: the detail behind the top of the page. |

## 2. Core terms

| Term | Meaning |
|---|---|
| **Snapshot** | One daily export of the active loan book. `loans_snapshot` keeps every snapshot (history); `loans_current` keeps only the latest. |
| **Outstanding principal** | The `outstanding_balance` column: principal still owed, excluding interest, fees and penalties. |
| **Days in arrears** | Instalments due minus instalments paid, in days (daily repayment cadence). |
| **Champion** | The collections officer responsible for a loan. Names are pseudonyms ("Champion 07"). |
| **Team / troop** | The team a champion belongs to. |
| **Active loan** | A loan present in the export: not yet completed, and not yet written off. |
| **Cold** | No payment for more than 7 days (`COLD_THRESHOLD_DAYS`). |
| **Escalate** | No payment for more than 30 days (`ESCALATE_THRESHOLD_DAYS`). Escalate is a subset of cold. |

## 3. PAR bands (colour = state)

Bands follow the source system's days-in-arrears categories.

| Band | Days in arrears | Colour |
|---|---|---|
| Performing | 0 | green |
| Watch | 1 | yellow-green |
| Substandard | 2 | amber |
| Doubtful | 3 | orange |
| Loss | 4 or more | red |

The source system spells the 0-day label "Perfoming" in `performance_category`. That is preserved in the stored data; the dashboard uses the clean `par_band` value.

Colour is used for state only: the five bands above, plus green / orange / red on the headline verdict. Every other chart uses one neutral teal.

## 4. Headline metrics

| Metric | Formula | Notes |
|---|---|---|
| **PAR% (portfolio at risk)** | Σ outstanding principal where days in arrears > 0 ÷ Σ outstanding principal | By balance, not loan count. Verdict badge: below 10% healthy, 10–20% elevated, above 20% high. **These bands are illustrative, not a standard.** |
| **Delta vs previous snapshot** | Latest value minus the previous snapshot's value, for the current filters | Shown in percentage points (pp). For PAR, red = worse, green = better. |
| **Collection efficiency** | Σ total amount received ÷ Σ total scheduled repayment | The schedule is **lifetime**, not due-to-date, so this is the share of the whole schedule collected so far. Loans early in their term naturally score lower. |
| **Outstanding principal (KES)** | Σ `outstanding_balance` | Delta is % change, shown neutral (growth is neither good nor bad by itself). |
| **Interest realization** | Σ interest paid ÷ Σ interest due | Lifetime basis, like collection efficiency. |
| **Sparklines** | Metric value at each snapshot | Only shown when there are 2+ snapshots. |

## 5. What changed (latest vs previous snapshot)

| Tile | Definition |
|---|---|
| **New loans** | Loan numbers present now but not in the previous snapshot. Help text gives KES approved. |
| **Loans closed or written off** | Present previously, absent now (completed, or removed from the active file). Help text gives principal that left. |
| **Newly in Loss** | In the Loss band now, and not in the Loss band at the previous snapshot. |
| **Newly cold** | Cold now (over 7 days without payment), and not cold at the previous snapshot. |

## 6. Needs attention flags

| Flag | Rule |
|---|---|
| **No payment > 30d** | `days_since_last_pay` > 30 (escalate). |
| **Early default** | In the Loss band **and** disbursed 60 days ago or less. An origination-quality signal, not a collections one. |
| **Newly in Loss** | As above. |

A loan can carry several flags; the table lists them together, largest balance first.

## 7. Risk tab

| Panel | What it shows | Rule / formula |
|---|---|---|
| **PAR banding** | Outstanding principal, loan count and % of book per band | Straight aggregation of `par_band`. |
| **Loss severity** | Loss-band loans split by time in arrears: 4–30d, 31–90d, 91–180d, 181–365d, 365d+ | A 10-day-old Loss loan and a 300-day-old one need different handling. |
| **Watch despite good standing** | Loans that are current today but have a poor history | 0 days in arrears **and** PAR AVG (historical average days in arrears) above the 75th percentile of that snapshot. The percentile is set in the ETL over the **whole** snapshot, so it does not shift when you filter. |
| **Under-collateralized** | Loans whose pledged security is below the loan | Collateral coverage = `security_amount` ÷ `approved_amount`; flagged when below 1.0×. |
| **Repossession events** | Loans with at least one repossession recorded | `repo_fee_count` > 0. |
| **Plan deviation** | Loans drifting from the repayment plan | `net_balance` − `schedule_net_balance`, flagged above KES 50. **The KES 50 threshold is a placeholder**, not statistically derived; treat the count as directional. |
| **Early defaults** | Loss band within 60 days of disbursement, by champion | Loan age = snapshot date − disbursement date. |
| **Concentration** | How much of the book sits with few champions, branches or loans | Share of outstanding principal. **HHI** = Σ (share)² on the 0–10,000 scale: under ~1,500 low, 1,500–2,500 moderate, over 2,500 high. A diagnostic, not a verdict. **Top 10 loans** = share of principal held by the ten largest loans. |

## 8. Collections tab

| Panel | Definition |
|---|---|
| **Overall collection efficiency** | Same formula as the headline. |
| **Per-loan efficiency histogram** | Each loan's received ÷ scheduled, 0–100%. |
| **Days since last payment** | Snapshot date − last pay date (capped at 60 on the chart), with cold and escalate thresholds marked. |
| **Follow-up lists** | *Cold*: 8–30 days without payment. *Escalate*: over 30 days. Sorted longest gap first. |
| **Champion leaderboard** | Per champion: loans, outstanding, collection efficiency, PAR% of their own book. The scatter plots PAR% against efficiency, bubble size = outstanding principal. Read the two together. |

## 9. Portfolio tab

| Panel | Definition |
|---|---|
| **Outstanding by branch / mix by product** | Share of outstanding principal, with loans and PAR% alongside. |
| **Expected yield** | Σ interest due ÷ Σ approved amount. |
| **Realized yield** | Σ interest paid ÷ Σ approved amount. |
| **Realization rate** | Interest paid ÷ interest due. The gap to 100% is scheduled interest not yet collected, a leakage separate from PAR (which covers principal only). |
| **Book over time** | Outstanding principal and active-loan count per snapshot, for the current filters. |
| **Vintage view** | Loans grouped by disbursement month, with each cohort's PAR%. **Current-snapshot only**: older cohorts are survivorship-biased because loans that finished well have already left the file. Default shows the last 12 cohorts. |

## 10. Data & system tab

| Panel | Definition |
|---|---|
| **Last successful load / rows** | Latest successful ETL run: extraction date and rows loaded. |
| **Failed runs, last 30 days** | Counted back from the most recent run (this is a static dataset, so "now" would be misleading). |
| **Run log** | `pipeline_run_log`. In this demo it is **simulated**: nightly timestamps plus two failed-then-retried runs. |
| **Assumptions in force** | Every threshold used, and where it is set. |

## 11. Data lineage

```
synthetic/generate.py  ->  raw daily exports (80-column layout)
        ->  etl.py (unmodified)  ->  loans_snapshot / loans_current / pipeline_run_log
        ->  dashboard/data.py (cached read, pandas filtering)
        ->  dashboard/metrics.py (formulas)  ->  app.py (layout)
```

Fields computed in the ETL: `par_band`, `loss_severity`, `watch_despite_good_standing`, `collateral_coverage`, `plan_deviation`, `plan_deviation_material_flag`, `days_since_last_pay`, `flag_cold`, `flag_escalate`, `collection_efficiency_pct`.
Computed in the app: PAR%, portfolio KPIs, early default, what-changed, HHI, cohort views.
