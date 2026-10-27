"""
Plotly chart builders with one consistent visual system.

Rules applied throughout (from the data-viz method this project follows):
  * one y-axis per chart - never dual-axis; two measures = two charts
  * categorical hues in fixed order; status colours only where colour MEANS
    good/bad, always paired with a text label
  * thin marks, 4px rounded bar ends, 2px lines, hairline solid grid
  * text in ink colours, never series colours
  * every chart has a hover tooltip
"""

import pandas as pd
import plotly.graph_objects as go

# Reference palette (light surface). Slots 1-3 validate all-pairs for CVD.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"
NEUTRAL = "#c3c2b7"
ORDINAL_BLUE = ["#184f95", "#256abf", "#5598e7", "#86b6ef"]   # dark -> light

SURFACE = "#fcfcfb"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _base(fig: go.Figure, title: str, height: int = 340, y_title: str = "",
          x_title: str = "", legend: bool = False) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=INK), x=0, xanchor="left"),
        height=height,
        margin=dict(l=64, r=24, t=56, b=56),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=12, color=INK_2),
        hoverlabel=dict(bgcolor="white", bordercolor=AXIS, font=dict(family=FONT, color=INK)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                    title_text="", font=dict(color=INK_2)),
        barcornerradius=4,
        bargap=0.35,
    )
    fig.update_xaxes(title_text=x_title, showgrid=False, linecolor=AXIS, automargin=True,
                     tickfont=dict(color=MUTED), title_font=dict(color=MUTED), title_standoff=12)
    fig.update_yaxes(title_text=y_title, gridcolor=GRID, gridwidth=1, zeroline=False, automargin=True,
                     linecolor=AXIS, tickfont=dict(color=MUTED), title_font=dict(color=MUTED),
                     title_standoff=12)
    return fig


def monthly_orders(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df["month"], y=df["orders"], marker_color=SERIES[0], name="Orders",
        hovertemplate="%{x|%b %Y}<br><b>%{y:,}</b> orders<extra></extra>"))
    return _base(fig, "Orders per month", y_title="Orders")


def monthly_on_time(df: pd.DataFrame, platform_rate: float) -> go.Figure:
    on_time = 100 - df["rate"]
    fig = go.Figure(go.Scatter(
        x=df["month"], y=on_time, mode="lines+markers", name="On-time %",
        line=dict(color=SERIES[0], width=2), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
        customdata=df[["delivered", "late"]],
        hovertemplate="%{x|%b %Y}<br><b>%{y:.1f}%</b> on time"
                      "<br>%{customdata[0]:,} delivered, %{customdata[1]:,} late<extra></extra>"))
    fig.add_hline(y=100 - platform_rate, line=dict(color=MUTED, width=1),
                  annotation_text=f"overall {100 - platform_rate:.1f}%",
                  annotation_font=dict(color=MUTED, size=11), annotation_position="bottom left")
    fig = _base(fig, "On-time delivery rate by purchase month", y_title="On time (%)")
    fig.update_yaxes(range=[min(70, float(on_time.min()) - 2), 100])
    return fig


def stage_comparison(df: pd.DataFrame) -> go.Figure:
    stages = ["Payment", "Seller fulfilment", "Transit"]
    colors = {"On Time": GOOD, "Late": CRITICAL}
    fig = go.Figure()
    for status in ["On Time", "Late"]:
        row = df[df["otd_status"] == status]
        if row.empty:
            continue
        r = row.iloc[0]
        fig.add_bar(
            y=stages, x=[r[s] for s in stages], orientation="h", name=f"{status} (n={int(r['orders']):,})",
            marker=dict(color=colors[status], line=dict(color=SURFACE, width=2)),
            text=[f"{r[s]:.1f} d" for s in stages], textposition="outside",
            textfont=dict(color=INK_2),
            hovertemplate=f"<b>{status}</b><br>%{{y}}: %{{x:.2f}} days<extra></extra>")
    fig = _base(fig, "Average days per stage: on-time vs late orders", x_title="Days", legend=True)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    longest = float(df[stages].max().max()) if not df.empty else 1.0
    fig.update_xaxes(showgrid=True, gridcolor=GRID, range=[0, longest * 1.15])
    return fig


def stage_trend(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for i, stage in enumerate(["Transit", "Seller fulfilment", "Payment"]):
        fig.add_scatter(x=df["month"], y=df[stage], mode="lines", name=stage,
                        line=dict(color=SERIES[i], width=2),
                        hovertemplate=f"%{{x|%b %Y}}<br>{stage}: <b>%{{y:.2f}} days</b><extra></extra>")
    fig = _base(fig, "Average days per stage by purchase month", y_title="Days", legend=True)
    fig.update_layout(hovermode="x unified")
    return fig


def late_rate_bars(df: pd.DataFrame, x: str, title: str, platform_rate: float,
                   x_title: str = "", height: int = 340, label_side: str = "left") -> go.Figure:
    """`label_side` puts the reference-line label over the shorter bars."""
    fig = go.Figure(go.Bar(
        x=df[x].astype(str), y=df["rate"], marker_color=SERIES[0], name="Late %",
        error_y=dict(type="data", symmetric=False, array=df["ci_high"] - df["rate"],
                     arrayminus=df["rate"] - df["ci_low"], color=INK_2, thickness=1, width=3),
        customdata=df[["delivered", "late", "ci_low", "ci_high"]],
        hovertemplate="<b>%{x}</b><br>Late: <b>%{y:.1f}%</b> (95% CI %{customdata[2]:.1f}-%{customdata[3]:.1f}%)"
                      "<br>%{customdata[1]:,} late of %{customdata[0]:,} delivered<extra></extra>"))
    fig.add_hline(y=platform_rate, line=dict(color=MUTED, width=1),
                  annotation_text=f"overall {platform_rate:.1f}%",
                  annotation_font=dict(color=MUTED, size=11), annotation_position=f"top {label_side}",
                  annotation_bgcolor=SURFACE)
    return _base(fig, title, height=height, y_title="Late deliveries (%)", x_title=x_title)


def seller_scatter(df: pd.DataFrame, platform_rate: float) -> go.Figure:
    fig = go.Figure()
    for flagged, name, color, size in [(False, "Not flagged", NEUTRAL, 7),
                                       (True, "Significantly late (flagged)", CRITICAL, 9)]:
        sub = df[df["late_rate_flag"] == flagged]
        fig.add_scatter(
            x=sub["n_orders"], y=100 * sub["late_rate_raw"], mode="markers", name=name,
            marker=dict(color=color, size=size, opacity=0.85, line=dict(color=SURFACE, width=2)),
            customdata=sub[["seller_id", "state", "late_rate_ci_low", "late_rate_ci_high",
                            "seller_score", "performance_tier"]],
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>%{x:,} orders"
                          "<br>Late: <b>%{y:.1f}%</b> (95% CI %{customdata[2]:.1%}-%{customdata[3]:.1%})"
                          "<br>Score %{customdata[4]:.1f} · %{customdata[5]}<extra></extra>")
    fig.add_hline(y=platform_rate, line=dict(color=MUTED, width=1),
                  annotation_text=f"platform {platform_rate:.1f}%",
                  annotation_font=dict(color=MUTED, size=11), annotation_position="top right")
    fig = _base(fig, "Seller late rate vs order volume (ranked sellers)", height=420,
                x_title="Orders (log scale)", y_title="Late deliveries (%)", legend=True)
    ticks = [t for t in [30, 50, 100, 200, 500, 1000, 2000] if t <= max(df["n_orders"].max(), 30) * 1.5]
    fig.update_xaxes(type="log", showgrid=True, gridcolor=GRID, tickvals=ticks,
                     ticktext=[f"{t:,}" for t in ticks], minor=dict(showgrid=False))
    return fig


def tier_bars(counts: pd.Series) -> go.Figure:
    order = ["Excellent", "Good", "At Risk", "Critical"]
    vals = [int(counts.get(t, 0)) for t in order]
    fig = go.Figure(go.Bar(
        x=order, y=vals, marker_color=ORDINAL_BLUE, text=vals, textposition="outside",
        textfont=dict(color=INK_2), hovertemplate="<b>%{x}</b><br>%{y} sellers<extra></extra>"))
    fig = _base(fig, "Ranked sellers by tier (relative)", y_title="Sellers")
    fig.update_yaxes(range=[0, max(vals) * 1.18 if vals else 1])
    return fig


def demand_line(weekly: pd.DataFrame, category: str) -> go.Figure:
    anomalies = weekly[weekly["anomaly"] != "Normal"]
    fig = go.Figure()
    fig.add_scatter(x=weekly["week_start"], y=weekly["n_items_sold"], mode="lines",
                    name="Units sold", line=dict(color=SERIES[0], width=2),
                    hovertemplate="Week of %{x|%d %b %Y}<br><b>%{y}</b> units<extra></extra>")
    if not anomalies.empty:
        fig.add_scatter(x=anomalies["week_start"], y=anomalies["n_items_sold"], mode="markers",
                        name="Anomaly week (|Z| > 2)",
                        marker=dict(color=SERIES[1], size=10, line=dict(color=SURFACE, width=2)),
                        customdata=anomalies[["z_score", "anomaly"]],
                        hovertemplate="Week of %{x|%d %b %Y}<br><b>%{y}</b> units"
                                      "<br>%{customdata[1]}, Z = %{customdata[0]:.1f}<extra></extra>")
    fig = _base(fig, f"Weekly units sold: {category}", height=360, y_title="Units", legend=True)
    fig.update_yaxes(rangemode="tozero")
    return fig


def stage_timings(log: dict) -> go.Figure:
    stages = pd.DataFrame(log["stages"])
    fig = go.Figure(go.Bar(
        y=stages["stage"], x=stages["seconds"], orientation="h", marker_color=SERIES[0],
        text=[f"{s:.1f}s" for s in stages["seconds"]], textposition="outside",
        textfont=dict(color=INK_2), hovertemplate="%{y}: <b>%{x:.2f}s</b><extra></extra>"))
    fig = _base(fig, f"Pipeline stage timings (total {log['total_seconds']:.1f}s)",
                height=380, x_title="Seconds")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=True, gridcolor=GRID, range=[0, float(stages["seconds"].max()) * 1.2])
    return fig


# ------------------------------------------------------------------ model outputs
# Predictions are drawn with an open/dashed style so they never read as
# observed history.

def calibration_chart(rel: pd.DataFrame, model_name: str) -> go.Figure:
    top = 100 * float(max(rel["mean_predicted"].max(), rel["observed_rate"].max())) * 1.1
    fig = go.Figure()
    fig.add_scatter(x=[0, top], y=[0, top], mode="lines", name="Perfect calibration",
                    line=dict(color=AXIS, width=1), hoverinfo="skip")
    fig.add_scatter(x=100 * rel["mean_predicted"], y=100 * rel["observed_rate"], mode="lines+markers",
                    name=f"{model_name} (predicted)",
                    line=dict(color=SERIES[0], width=2, dash="dash"),
                    marker=dict(size=9, color=SURFACE, line=dict(color=SERIES[0], width=2)),
                    customdata=rel["n"],
                    hovertemplate="Predicted %{x:.1f}% · observed <b>%{y:.1f}%</b>"
                                  "<br>%{customdata:,} orders<extra></extra>")
    fig = _base(fig, "Calibration: predicted vs observed late rate (deciles)", height=360,
                x_title="Mean predicted probability (%)", y_title="Observed late rate (%)", legend=True)
    return fig


def risk_band_bars(bands: pd.DataFrame) -> go.Figure:
    order = ["Low", "Medium", "High", "Critical"]
    b = bands.set_index("risk_band").reindex(order).fillna(0).reset_index()
    fig = go.Figure(go.Bar(
        x=b["risk_band"], y=100 * b["observed_late_rate"], marker_color=ORDINAL_BLUE[::-1],
        text=[f"{100 * r:.1f}%<br>n={int(n):,}" for r, n in zip(b["observed_late_rate"], b["n"])],
        textposition="outside", textfont=dict(color=INK_2),
        hovertemplate="<b>%{x}</b> predicted risk<br>Actually late: %{y:.1f}%<extra></extra>"))
    fig = _base(fig, "Actual late rate by predicted risk band", height=360,
                x_title="Predicted risk band", y_title="Actually late (%)")
    fig.update_yaxes(range=[0, float(100 * b["observed_late_rate"].max()) * 1.3 + 1])
    return fig


def importance_bars(imp: pd.DataFrame, model_name: str) -> go.Figure:
    imp = imp.head(12).iloc[::-1]
    fig = go.Figure(go.Bar(
        y=imp["feature"], x=imp["mean_abs_shap"], orientation="h", marker_color=SERIES[0],
        hovertemplate="%{y}: <b>%{x:.3f}</b> mean |SHAP| (log-odds)<extra></extra>"))
    fig = _base(fig, f"What the model relies on (SHAP, {model_name})", height=400,
                x_title="Mean |SHAP value| (log-odds)")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    return fig
