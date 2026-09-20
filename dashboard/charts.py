"""Altair charts. Colour rules: the five PAR states get state colours; everything else is one
neutral series colour (teal) or a muted grey. No rainbow palettes."""
from __future__ import annotations

import altair as alt
import pandas as pd

from dashboard.metrics import PAR_BANDS, LOSS_SEVERITY

PRIMARY = "#3E8E8A"      # neutral series colour
MUTED = "#6B7480"        # secondary series / reference lines
LOSS_RED = "#C4432B"
STATE = {"Performing": "#4C9A6A", "Watch": "#8FA84E", "Substandard": "#D9A63E",
         "Doubtful": "#D97D3D", "Loss": "#C4432B"}
HEIGHT = 280


def _kes(title: str) -> alt.Axis:
    return alt.Axis(title=title, format="~s", grid=True)


def par_band_bar(band: pd.DataFrame) -> alt.Chart:
    d = band.reset_index().rename(columns={"par_band": "Band"})
    return (alt.Chart(d).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(x=alt.X("Band:N", sort=PAR_BANDS, title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("balance:Q", axis=_kes("Outstanding principal (KES)")),
                    color=alt.Color("Band:N", scale=alt.Scale(domain=PAR_BANDS, range=[STATE[b] for b in PAR_BANDS]), legend=None),
                    tooltip=[alt.Tooltip("Band:N"), alt.Tooltip("loans:Q", title="Loans", format=","),
                             alt.Tooltip("balance:Q", title="Outstanding (KES)", format=",.0f"),
                             alt.Tooltip("share:Q", title="% of book", format=".1f")])
            .properties(height=HEIGHT))


def loss_severity_bar(d: pd.DataFrame) -> alt.Chart:
    d = d.reset_index().rename(columns={"loss_severity": "Days in arrears"})
    return (alt.Chart(d).mark_bar(color=LOSS_RED, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(x=alt.X("Days in arrears:N", sort=LOSS_SEVERITY, title="Days in arrears", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("balance:Q", axis=_kes("Outstanding principal (KES)")),
                    tooltip=[alt.Tooltip("Days in arrears:N"), alt.Tooltip("loans:Q", title="Loans", format=","),
                             alt.Tooltip("balance:Q", title="Outstanding (KES)", format=",.0f")])
            .properties(height=HEIGHT))


def hbar(d: pd.DataFrame, cat: str, val: str, val_title: str, fmt: str = ",.1f", height: int | None = None) -> alt.Chart:
    """Sorted horizontal bars, single colour."""
    return (alt.Chart(d).mark_bar(color=PRIMARY, cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
            .encode(y=alt.Y(f"{cat}:N", sort="-x", title=None),
                    x=alt.X(f"{val}:Q", title=val_title),
                    tooltip=[alt.Tooltip(f"{cat}:N"), alt.Tooltip(f"{val}:Q", title=val_title, format=fmt)])
            .properties(height=height or max(120, 26 * len(d))))


def hist(d: pd.DataFrame, col: str, title: str, maxbins: int = 30, rules: list[tuple[float, str, str]] | None = None,
         extent: tuple[float, float] | None = None) -> alt.Chart:
    x = alt.X(f"{col}:Q", bin=alt.Bin(maxbins=maxbins, extent=list(extent)) if extent else alt.Bin(maxbins=maxbins), title=title)
    base = alt.Chart(d).mark_bar(color=PRIMARY, opacity=0.9).encode(x=x, y=alt.Y("count():Q", title="Loans"))
    layers = [base]
    for xv, label, colour in (rules or []):
        r = pd.DataFrame({"x": [xv], "label": [label]})
        layers.append(alt.Chart(r).mark_rule(color=colour, strokeDash=[5, 4], strokeWidth=2).encode(x="x:Q"))
        layers.append(alt.Chart(r).mark_text(color=colour, align="left", dx=5, dy=-4, baseline="bottom", fontSize=11)
                      .encode(x="x:Q", y=alt.value(0), text="label:N"))
    return alt.layer(*layers).properties(height=HEIGHT)


def trend_line(d: pd.DataFrame, x: str, y: str, y_title: str, fmt: str = ".1f") -> alt.Chart:
    """Line + markers (never smoothed - short histories shouldn't imply precision)."""
    base = alt.Chart(d).encode(
        x=alt.X(f"{x}:T", title=None, axis=alt.Axis(format="%d %b")),
        y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(zero=False, nice=True)),
        tooltip=[alt.Tooltip(f"{x}:T", title="Snapshot", format="%d %b %Y"), alt.Tooltip(f"{y}:Q", title=y_title, format=fmt)])
    return (base.mark_line(color=PRIMARY, strokeWidth=2.5) + base.mark_point(color=PRIMARY, filled=True, size=45)).properties(height=HEIGHT)


def champion_scatter(d: pd.DataFrame) -> alt.Chart:
    d = d.reset_index()
    return (alt.Chart(d).mark_circle(color=PRIMARY, opacity=0.75)
            .encode(x=alt.X("par:Q", title="PAR % of champion's book", scale=alt.Scale(zero=False)),
                    y=alt.Y("ce:Q", title="Collection efficiency %", scale=alt.Scale(zero=False)),
                    size=alt.Size("outstanding:Q", legend=None, scale=alt.Scale(range=[60, 900])),
                    tooltip=[alt.Tooltip("collection_champ_name:N", title="Champion"), alt.Tooltip("loans:Q", title="Loans", format=","),
                             alt.Tooltip("outstanding:Q", title="Outstanding (KES)", format=",.0f"),
                             alt.Tooltip("par:Q", title="PAR %", format=".1f"), alt.Tooltip("ce:Q", title="Collection eff. %", format=".1f")])
            .properties(height=320))


def grouped_yield(d: pd.DataFrame) -> alt.Chart:
    long = d.reset_index().melt(id_vars="loan_product_type_name", value_vars=["yield_expected", "yield_realized"],
                                var_name="kind", value_name="pct")
    long["kind"] = long["kind"].map({"yield_expected": "Expected (interest due)", "yield_realized": "Realized (interest paid)"})
    return (alt.Chart(long).mark_bar()
            .encode(y=alt.Y("loan_product_type_name:N", title=None, sort=alt.SortField("pct", order="descending")),
                    x=alt.X("pct:Q", title="% of approved amount"),
                    yOffset="kind:N",
                    color=alt.Color("kind:N", title=None, scale=alt.Scale(domain=["Expected (interest due)", "Realized (interest paid)"], range=[MUTED, PRIMARY]),
                                    legend=alt.Legend(orient="bottom")),
                    tooltip=[alt.Tooltip("loan_product_type_name:N", title="Product"), alt.Tooltip("kind:N", title=""), alt.Tooltip("pct:Q", title="%", format=".1f")])
            .properties(height=max(200, 44 * d.shape[0])))


def vintage(d: pd.DataFrame) -> alt.LayerChart:
    d = d.reset_index()
    bars = alt.Chart(d).mark_bar(color=PRIMARY, opacity=0.55).encode(
        x=alt.X("disb_month:N", title="Disbursement month", axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("loans:Q", title="Loans still active"),
        tooltip=[alt.Tooltip("disb_month:N", title="Cohort"), alt.Tooltip("loans:Q", title="Loans", format=","), alt.Tooltip("par:Q", title="PAR %", format=".1f")])
    line = alt.Chart(d).mark_line(color=MUTED, point=alt.OverlayMarkDef(color=MUTED, filled=True)).encode(
        x="disb_month:N", y=alt.Y("par:Q", title="PAR % of cohort", axis=alt.Axis(orient="right")))
    return alt.layer(bars, line).resolve_scale(y="independent").properties(height=HEIGHT)


def book_over_time(d: pd.DataFrame) -> alt.Chart:
    return trend_line(d, "extraction_date", "outstanding", "Outstanding principal (KES)", fmt=",.0f")
