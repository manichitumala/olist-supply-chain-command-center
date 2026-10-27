"""
Supply Chain Command Center - Streamlit dashboard.

    streamlit run src/dashboard/app.py

Reads the gold Parquet layer and analysis exports produced by
`python -m src.pipeline`. Every figure shown is a historical observation;
model predictions will be added in a later phase and labelled as such.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import MIN_SELLER_ORDERS, get_settings  # noqa: E402
from src.dashboard import charts, data  # noqa: E402

st.set_page_config(page_title="Olist Supply Chain Command Center", page_icon="📦", layout="wide")
settings = get_settings()

missing = data.missing_inputs(settings)
if missing:
    st.title("Olist Supply Chain Command Center")
    st.error("Pipeline outputs not found. Run `python -m src.pipeline` first.")
    st.code("\n".join(missing))
    st.stop()


@st.cache_resource
def get_con():
    return data.connect(settings)


@st.cache_data
def load_export(name: str, parse_dates: tuple = ()) -> pd.DataFrame:
    return data.read_export(settings, name, parse_dates=list(parse_dates))


con = get_con()
win_start, win_end = data.analysis_window(con)
CHART_CFG = {"displaylogo": False}


def show(fig):
    st.plotly_chart(fig, width="stretch", config=CHART_CFG, theme=None)


# ------------------------------------------------------------------ header
st.title("Olist Supply Chain Command Center")
st.caption(
    "Brazilian e-commerce marketplace, 99,441 orders (2016-2018). "
    "Tabs show **historical observations**, except *Delivery risk (model)*, which shows clearly "
    "labelled **model predictions**. "
    "Late = delivered after the promised calendar date.")

f1, f2, _ = st.columns([2, 2, 3])
with f1:
    picked_regions = st.multiselect("Customer region", data.regions(con), placeholder="All regions")
with f2:
    period = st.date_input("Purchase date", value=(win_start, win_end),
                           min_value=win_start, max_value=win_end, format="YYYY-MM-DD")
start, end = (period if isinstance(period, tuple) and len(period) == 2 else (win_start, win_end))
flt = data.Filters(regions=tuple(picked_regions), start=start, end=end)

kpi = data.headline(con, flt)
if not kpi["orders"]:
    st.warning("No orders match these filters.")
    st.stop()
platform_late = 100 * kpi["late"] / kpi["delivered"] if kpi["delivered"] else 0.0

tabs = st.tabs(["Executive", "Delivery & fulfilment", "Regions", "Sellers",
                "Demand & risk", "Delivery risk (model)", "Data quality"])

# ------------------------------------------------------------------ executive
with tabs[0]:
    c = st.columns(6)
    c[0].metric("Orders (selected period)", f"{kpi['orders']:,.0f}", help="All statuses, including cancelled")
    c[1].metric("Unique customers", f"{kpi['customers']:,.0f}", help="customer_unique_id, not customer_id")
    c[2].metric("GMV", f"R$ {kpi['gmv'] / 1e6:,.2f}M", help="Item value, excluding cancelled/unavailable orders")
    c[3].metric("On-time delivery", f"{kpi['otd_pct']:.2f}%", help="Delivered orders, judged on calendar date")
    c[4].metric("Avg delivery time", f"{kpi['lead_days']:.1f} days")
    c[5].metric("Avg review", f"{kpi['review']:.2f} / 5")

    m = data.monthly(con, flt)
    left, right = st.columns(2)
    with left:
        show(charts.monthly_orders(m))
    with right:
        show(charts.monthly_on_time(m, platform_late))
    st.caption(
        f"{kpi['late']:,.0f} late deliveries · cancellation rate {kpi['cancel_pct']:.2f}% · "
        f"trends limited to the analysis window ({win_start} to {win_end}); "
        "the sparse 2016 and Sep-Oct 2018 months are excluded.")

# ------------------------------------------------------------------ delivery
with tabs[1]:
    stages = data.stage_by_status(con, flt)
    left, right = st.columns(2)
    with left:
        show(charts.stage_comparison(stages))
    with right:
        show(charts.late_rate_bars(data.late_by_distance(con, flt), "distance_band",
                                   "Late rate by seller-customer distance", platform_late,
                                   x_title="Distance band"))
    show(charts.stage_trend(data.monthly_stages(con, flt)))
    if {"On Time", "Late"} <= set(stages["otd_status"]):
        s = stages.set_index("otd_status")
        st.info(
            f"Late orders spend **{s.loc['Late', 'Transit'] / s.loc['On Time', 'Transit']:.1f}x** longer "
            f"in transit and **{s.loc['Late', 'Seller fulfilment'] / s.loc['On Time', 'Seller fulfilment']:.1f}x** "
            "longer in seller fulfilment than on-time orders: transport is the main lever, "
            "seller fulfilment the second.")

# ------------------------------------------------------------------ regions
with tabs[2]:
    states = data.late_by_state(con, flt)
    show(charts.late_rate_bars(states, "state", "Late rate by customer state (>= 30 delivered orders)",
                               platform_late, x_title="Customer state", height=380,
                               label_side="right"))
    st.caption("Error bars are 95% Wilson confidence intervals; small states have wide intervals.")
    st.subheader("Transport hotspots")
    st.caption("Distance band x customer region, >= 100 delivered orders, all dates and regions.")
    hot = load_export("root_cause_transport_delay.csv")
    st.dataframe(
        hot[["distance_band", "region", "n_orders", "n_late", "late_rate_pct",
             "late_ci_low_pct", "late_ci_high_pct", "avg_transit_days"]],
        hide_index=True, width="stretch",
        column_config={
            "distance_band": "Distance", "region": "Customer region",
            "n_orders": st.column_config.NumberColumn("Delivered", format="localized"),
            "n_late": st.column_config.NumberColumn("Late", format="localized"), "late_rate_pct": st.column_config.NumberColumn("Late %", format="%.1f"),
            "late_ci_low_pct": st.column_config.NumberColumn("CI low %", format="%.1f"),
            "late_ci_high_pct": st.column_config.NumberColumn("CI high %", format="%.1f"),
            "avg_transit_days": st.column_config.NumberColumn("Avg transit (d)", format="%.1f"),
        })

# ------------------------------------------------------------------ sellers
with tabs[3]:
    sc = load_export("seller_scorecard.csv")
    ranked = sc[sc["seller_score"].notna()].copy()
    platform_seller_late = 100 * sc["n_late"].sum() / sc["n_delivered"].sum()
    st.caption(
        f"{len(ranked):,} of {len(sc):,} sellers have >= {MIN_SELLER_ORDERS} orders and are ranked. "
        "Tiers are **relative** (top 25% / 50% / 15% / bottom 10%). The **flag** is absolute: the "
        "95% lower bound of the seller's late rate is above the platform rate. "
        "Seller views cover all dates and regions.")

    s1, s2, s3 = st.columns([2, 2, 1])
    with s1:
        st_pick = st.multiselect("Seller state", sorted(ranked["state"].dropna().unique()),
                                 placeholder="All states")
    with s2:
        tier_pick = st.multiselect("Tier", ["Excellent", "Good", "At Risk", "Critical"],
                                   placeholder="All tiers")
    with s3:
        only_flagged = st.toggle("Flagged only")
    view = ranked
    if st_pick:
        view = view[view["state"].isin(st_pick)]
    if tier_pick:
        view = view[view["performance_tier"].isin(tier_pick)]
    if only_flagged:
        view = view[view["late_rate_flag"]]

    m1, m2, m3 = st.columns(3)
    m1.metric("Sellers shown", f"{len(view):,}")
    m2.metric("Flagged (significantly late)", f"{int(view['late_rate_flag'].sum()):,}")
    m3.metric("Platform late rate", f"{platform_seller_late:.2f}%")

    left, right = st.columns([3, 2])
    with left:
        show(charts.seller_scatter(view, platform_seller_late))
    with right:
        show(charts.tier_bars(view["performance_tier"].value_counts()))

    st.dataframe(
        view.sort_values(["late_rate_flag", "late_rate_ci_low"], ascending=[False, False])[
            ["seller_id", "state", "n_orders", "late_rate_raw", "late_rate_ci_low", "late_rate_ci_high",
             "avg_fulfilment_days", "missed_limit_rate_raw", "avg_review_adj", "seller_score",
             "performance_tier", "late_rate_flag"]],
        hide_index=True, width="stretch", height=360,
        column_config={
            "seller_id": "Seller", "state": "State", "n_orders": "Orders",
            "late_rate_raw": st.column_config.NumberColumn("Late %", format="percent"),
            "late_rate_ci_low": st.column_config.NumberColumn("CI low", format="percent"),
            "late_rate_ci_high": st.column_config.NumberColumn("CI high", format="percent"),
            "avg_fulfilment_days": st.column_config.NumberColumn("Fulfilment (d)", format="%.1f"),
            "missed_limit_rate_raw": st.column_config.NumberColumn("Missed ship limit", format="percent"),
            "avg_review_adj": st.column_config.NumberColumn("Review (adj.)", format="%.2f"),
            "seller_score": st.column_config.NumberColumn("Score", format="%.1f"),
            "performance_tier": "Tier", "late_rate_flag": "Flagged",
        })

# ------------------------------------------------------------------ demand & risk
with tabs[4]:
    weekly = load_export("demand_weekly_detail.csv", parse_dates=("week_start",))
    summary = load_export("demand_variability_by_category.csv")
    classified = summary[summary["demand_class"] != "Insufficient data"]
    st.caption("Category views cover all regions over the full weeks of the analysis window.")

    cats = classified.sort_values("total_items", ascending=False)["category_en"].tolist()
    cat = st.selectbox("Category", cats, index=0)
    show(charts.demand_line(weekly[weekly["category_en"] == cat], cat))
    row = classified.set_index("category_en").loc[cat]
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Units sold", f"{row['total_items']:,.0f}")
    d2.metric("Weekly CV", f"{row['coefficient_of_variation']:.2f}", help=row["demand_class"])
    d3.metric("Zero-sales weeks", f"{100 * row['zero_week_share']:.0f}%")
    d4.metric("Demand pattern", row["sbc_class"], help="Syntetos-Boylan classification")

    left, right = st.columns([2, 3])
    with left:
        st.subheader("Demand classification")
        st.dataframe(
            classified[["category_en", "total_items", "coefficient_of_variation", "sbc_class"]],
            hide_index=True, width="stretch", height=380,
            column_config={
                "category_en": "Category",
                "total_items": st.column_config.NumberColumn("Units", format="localized"),
                "coefficient_of_variation": st.column_config.NumberColumn("CV", format="%.2f"),
                "sbc_class": "Pattern",
            })
    with right:
        st.subheader("Supply Chain Risk Index")
        st.caption("A relative ranking across categories, not a probability. Top 20% = High.")
        risk = load_export("supply_chain_risk_index.csv")
        st.dataframe(
            risk[["category_en", "demand_risk", "delivery_risk",
                  "seller_risk", "supply_chain_risk", "risk_tier"]],
            hide_index=True, width="stretch", height=380,
            column_config={
                "category_en": "Category",
                "demand_risk": st.column_config.ProgressColumn("Demand", min_value=0, max_value=100, format="%.0f", width="small"),
                "delivery_risk": st.column_config.ProgressColumn("Delivery", min_value=0, max_value=100, format="%.0f", width="small"),
                "seller_risk": st.column_config.ProgressColumn("Seller", min_value=0, max_value=100, format="%.0f", width="small"),
                "supply_chain_risk": st.column_config.NumberColumn("Risk", format="%.1f"),
                "risk_tier": "Tier",
            })

# ------------------------------------------------------------------ delivery risk model
with tabs[5]:
    pred_path = settings.data_dir / "models" / "delay_predictions.parquet"
    metrics_path = settings.exports_dir / "delay_model_metrics.json"
    if not (pred_path.exists() and metrics_path.exists()):
        st.info("The delay model has not been trained yet. Run `python -m src.pipeline`.")
    else:
        mx = json.loads(metrics_path.read_text(encoding="utf-8"))
        best = mx["selected_model"]
        rep = mx["report"][best]
        st.warning(
            "**Model predictions, not observed history.** Each order was scored at payment approval "
            "by a model trained only on orders delivered before that month began. The *actual* "
            "outcome column is shown for evaluation; it was unknown when the prediction was made.",
            icon="🔮")
        k = st.columns(4)
        k[0].metric("Model", best, help="Chosen on Jan-Mar 2018 before the reported months were scored")
        k[1].metric("ROC-AUC (Apr-Aug, monthly mean)", f"{rep['roc_auc_monthly_mean']:.3f}")
        k[2].metric("PR-AUC (Apr-Aug, monthly mean)", f"{rep['pr_auc_monthly_mean']:.3f}",
                    help=f"A random score would get the late rate, about {rep['late_rate_monthly_mean']:.3f}")
        k[3].metric("Late orders caught in top 10%", f"{rep['recall_top10_monthly_mean']:.0%}",
                    help=f"{rep['precision_top10_monthly_mean']:.0%} of the riskiest 10% were actually late")

        @st.cache_data
        def load_predictions(path: str) -> pd.DataFrame:
            return pd.read_parquet(path)

        preds = load_predictions(str(pred_path))
        r1, r2, r3 = st.columns([2, 3, 2])
        with r1:
            month = st.selectbox("Purchase month", sorted(preds["month"].unique(), reverse=True))
        with r2:
            band_pick = st.multiselect("Predicted risk band", ["Critical", "High", "Medium", "Low"],
                                       placeholder="All bands")
        with r3:
            rank_by = st.radio("Rank by", ["Probability", "Value at risk"], horizontal=True)
        view = preds[preds["month"] == month]
        if band_pick:
            view = view[view["risk_band"].isin(band_pick)]
        view = view.sort_values("value_at_risk" if rank_by == "Value at risk" else "p_late", ascending=False)
        st.caption(
            f"{len(view):,} orders shown for {month} "
            f"({'reported period' if month in mx['report_months'] else 'model-selection period'}). "
            "Value at risk = probability x order value. Reasons are the features pushing the score up "
            "most (SHAP); they are available for the reported months.")
        st.dataframe(
            view[["order_id", "p_late", "risk_band", "value_at_risk", "top_reasons", "customer_state",
                  "seller_state", "main_category", "promised_days", "is_late"]].head(300),
            hide_index=True, width="stretch", height=380,
            column_config={
                "order_id": "Order", "p_late": st.column_config.ProgressColumn(
                    "P(late)", min_value=0, max_value=1, format="percent"),
                "risk_band": "Band",
                "value_at_risk": st.column_config.NumberColumn("Value at risk (R$)", format="%.2f"),
                "top_reasons": "Main reasons (model)", "customer_state": "Customer",
                "seller_state": "Seller", "main_category": "Category", "promised_days": "Promised (d)",
                "is_late": st.column_config.CheckboxColumn("Actually late"),
            })
        left, right = st.columns(2)
        with left:
            show(charts.calibration_chart(pd.DataFrame(mx["reliability_report"]), best))
        with right:
            show(charts.risk_band_bars(pd.DataFrame(mx["risk_bands_report"])))
        st.caption(
            "Ranking holds up (each band is later than the one below it), but the highest probabilities "
            "overshoot: they are re-levelled on the most recent 45 days, and after the Feb-Mar 2018 "
            "spike those days were worse than the months that followed. Use the probabilities as "
            "relative risk.")
        show(charts.importance_bars(pd.DataFrame(mx["feature_importance_shap"]), best))
        st.caption("Full method, baselines and limitations: `reports/delay_model.md`.")

# ------------------------------------------------------------------ data quality
with tabs[6]:
    st.caption("How the numbers above were produced: Bronze (raw) -> Silver (typed, flagged) -> "
               "Gold (star schema). Full audit in `reports/data_quality_report.md`.")
    left, right = st.columns([3, 2])
    with left:
        counts = data.layer_counts(settings)
        st.dataframe(counts, hide_index=True, width="stretch", height=420,
                     column_config={"layer": "Layer", "table": "Table",
                                    "rows": st.column_config.NumberColumn("Rows", format="localized"),
                                    "size_mb": st.column_config.NumberColumn("Parquet MB", format="%.2f")})
    with right:
        log_path = settings.data_dir / "run_log.json"
        if log_path.exists():
            show(charts.stage_timings(json.loads(log_path.read_text(encoding="utf-8"))))
    st.subheader("Issues found in the raw data, and how they are handled")
    st.dataframe(pd.DataFrame([
        ("Products missing category", "610", "'unknown'"),
        ("Category missing from translation file", "13 products", "Portuguese name kept"),
        ("Carrier handover before payment approved", "1,359 orders", "Flagged, excluded from lead times"),
        ("Delivered before carrier handover", "23 orders", "Flagged, excluded from lead times"),
        ("'delivered' with no delivered timestamp", "8 orders", "Flagged, treated as not delivered"),
        ("Delivered on the due date after midnight", "1,292 orders", "Judged on calendar date: on time"),
        ("Duplicate reviews", "551 orders", "Latest answered review kept"),
        ("Zip prefixes without geolocation", "157 customer / 7 seller", "State centroid fallback"),
        ("Orders with no items", "775", "Kept in fact_order (has_items = false)"),
    ], columns=["Issue", "Affected", "Handling"]), hide_index=True, width="stretch")
