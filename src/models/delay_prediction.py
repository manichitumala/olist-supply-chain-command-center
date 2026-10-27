"""
Delivery-delay prediction.

Question: at the moment an order's payment is approved, how likely is it to
be delivered after the date the customer was promised?

Features (sql/features/01_delay_features.sql) use only information known at
payment approval: the order, its items and payment, the promise, distance,
and point-in-time seller / route / platform history.

Evaluation is a monthly walk-forward backtest, because delivery conditions
shift sharply between months (late rate ~6% in 2017, ~15% in Feb-Mar 2018,
~4% in mid-2018). For each month M of 2018:
  * training data = orders whose label was KNOWN before M started
    (delivered before the 1st of M) - exactly what a team could use live
  * the most recent 45 days of that data calibrate the model (isotonic)
  * the model then predicts every order purchased in M
Months Jan-Mar 2018 select the model; Apr-Aug 2018 are the reported
out-of-sample results. Every prediction shown in the dashboard is an
out-of-sample prediction from a model trained only on earlier data.
"""

import json
from datetime import date, timedelta

import duckdb
import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.calibration import CalibratedClassifierCV  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.frozen import FrozenEstimator  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score, brier_score_loss, f1_score, log_loss,
    precision_recall_curve, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import (  # noqa: E402
    FunctionTransformer, OneHotEncoder, OrdinalEncoder, StandardScaler,
)
from xgboost import XGBClassifier  # noqa: E402

from src.config import Settings  # noqa: E402
from src.db import read_sql_file  # noqa: E402

SEED = 42
PRIOR_STRENGTH = 20.0          # pseudo-orders behind smoothed history rates
CALIBRATION_DAYS = 45
TOP_SHARE = 0.10               # operational view: act on the riskiest 10%
SELECTION_MONTHS = ["2018-01", "2018-02", "2018-03"]
REPORT_MONTHS = ["2018-04", "2018-05", "2018-06", "2018-07", "2018-08"]

NUMERIC = [
    "promised_days", "approval_hours", "days_to_shipping_limit",
    "purchase_month", "purchase_dow", "purchase_hour",
    "n_items", "n_distinct_sellers", "items_value", "freight_value", "freight_ratio",
    "total_weight_g", "total_volume_cm3", "n_categories",
    "max_installments", "n_payments", "same_state", "distance_km",
    "seller_prior_delivered", "seller_prior_orders", "seller_late_rate_hist",
    "seller_late_rate_90d", "route_prior_delivered", "route_late_rate_hist",
    "platform_late_rate_30d", "orders_prev_7d",
]
CATEGORICAL = ["customer_state", "seller_state", "main_category", "payment_type"]
FEATURES = NUMERIC + CATEGORICAL
RISK_BANDS = [(0.0, "Low"), (0.10, "Medium"), (0.25, "High"), (0.50, "Critical")]
MODEL_NAMES = ["Logistic Regression", "Random Forest", "XGBoost"]


# ------------------------------------------------------------------ data

def load_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute(read_sql_file("features/01_delay_features.sql").rstrip().rstrip(";")).df()
    df["purchase_ts"] = pd.to_datetime(df["purchase_ts"])
    df["delivered_ts"] = pd.to_datetime(df["delivered_ts"])
    df["month"] = df["purchase_ts"].dt.strftime("%Y-%m")
    return df


def add_history_rates(df: pd.DataFrame, prior_rate: float) -> pd.DataFrame:
    """Smoothed point-in-time late rates. `prior_rate` must come from data
    available at training time, never from the period being predicted."""
    out = df.copy()
    a, b = prior_rate * PRIOR_STRENGTH, (1 - prior_rate) * PRIOR_STRENGTH

    def smooth(late, n):
        return (out[late] + a) / (out[n] + a + b)

    out["seller_late_rate_hist"] = smooth("seller_prior_late", "seller_prior_delivered")
    out["route_late_rate_hist"] = smooth("route_prior_late", "route_prior_delivered")
    out["seller_late_rate_90d"] = smooth("seller_late_90d", "seller_delivered_90d")
    out["platform_late_rate_30d"] = (out["platform_late_30d"] / out["platform_delivered_30d"]
                                     .replace(0, np.nan)).fillna(prior_rate)
    return out


def known_before(df: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Orders whose outcome was observable before `cutoff`."""
    return df[df["delivered_ts"] < cutoff]


# ------------------------------------------------------------------ models

def signed_log1p(x):
    """Compresses heavy-tailed values (price, weight, history counts) for the linear model."""
    return np.sign(x) * np.log1p(np.abs(x))


def preprocessor(kind: str) -> ColumnTransformer:
    num_steps = [("impute", SimpleImputer(strategy="median"))]
    if kind == "onehot":
        num_steps += [("log", FunctionTransformer(signed_log1p, feature_names_out="one-to-one")),
                      ("scale", StandardScaler())]
        cat = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50, sparse_output=False)
    else:
        cat = Pipeline([("fill", SimpleImputer(strategy="constant", fill_value="missing")),
                        ("ord", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1))])
    return ColumnTransformer([("num", Pipeline(num_steps), NUMERIC), ("cat", cat, CATEGORICAL)])


def build_model(name: str) -> Pipeline:
    if name == "Logistic Regression":
        clf = LogisticRegression(max_iter=3000, C=0.5)
        return Pipeline([("prep", preprocessor("onehot")), ("clf", clf)])
    if name == "Random Forest":
        clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=25, max_features="sqrt",
                                     n_jobs=-1, random_state=SEED)
        return Pipeline([("prep", preprocessor("ordinal")), ("clf", clf)])
    if name == "XGBoost":
        clf = XGBClassifier(n_estimators=350, learning_rate=0.04, max_depth=4, min_child_weight=10,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0,
                            random_state=SEED, n_jobs=-1, tree_method="hist")
        return Pipeline([("prep", preprocessor("ordinal")), ("clf", clf)])
    raise ValueError(name)


def fit_calibrated(name: str, known: pd.DataFrame, cutoff: pd.Timestamp):
    """Fits on ALL known history, then re-levels probabilities with Platt
    (sigmoid) scaling on the most recent CALIBRATION_DAYS, the closest match to
    the conditions being predicted. Sigmoid scaling is monotonic, so it never
    changes how orders are ranked within a month; isotonic scaling was tried
    and rejected because its step function creates ties that hurt ranking.
    The calibration rows are also training rows: with two parameters, Platt
    scaling has little room to overfit them."""
    cal_part = known[known["purchase_ts"] >= cutoff - pd.Timedelta(days=CALIBRATION_DAYS)]
    model = build_model(name).fit(known[FEATURES], known["is_late"])
    calibrator = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
    calibrator.fit(cal_part[FEATURES], cal_part["is_late"])
    return model, calibrator


# ------------------------------------------------------------------ evaluation

def best_f1_threshold(y, p) -> float:
    prec, rec, thr = precision_recall_curve(y, p)
    f1 = 2 * prec * rec / np.clip(prec + rec, 1e-12, None)
    return float(thr[np.argmax(f1[:-1])]) if len(thr) else 0.5


def evaluate(y, p, threshold: float) -> dict:
    y, p = np.asarray(y), np.asarray(p)
    pred = p >= threshold
    k = max(1, int(round(TOP_SHARE * len(p))))
    top = np.argsort(-p, kind="stable")[:k]
    both = len(np.unique(y)) > 1
    return {
        "n": int(len(y)),
        "late_rate": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, p)) if both else float("nan"),
        "pr_auc": float(average_precision_score(y, p)) if both else float("nan"),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1])),
        "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision_top10": float(y[top].mean()),
        "recall_top10": float(y[top].sum() / max(1, y.sum())),
    }


def reliability_table(y, p, bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    df["bin"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False)
    return df.groupby("bin").agg(n=("y", "size"), mean_predicted=("p", "mean"),
                                 observed_rate=("y", "mean")).reset_index(drop=True)


def risk_band(p) -> np.ndarray:
    labels = np.array([lbl for _, lbl in RISK_BANDS])
    edges = np.array([lo for lo, _ in RISK_BANDS])
    return labels[np.searchsorted(edges, np.asarray(p), side="right") - 1]


# ------------------------------------------------------------------ explanation

def shap_matrix(model: Pipeline, X: pd.DataFrame, background: pd.DataFrame) -> np.ndarray:
    """SHAP values (log-odds) for the model actually being used, one column per
    ORIGINAL feature: one-hot columns of a categorical are summed back into it."""
    import shap
    prep, clf = model.named_steps["prep"], model.named_steps["clf"]
    Xt = prep.transform(X)
    if isinstance(clf, LogisticRegression):
        bg = prep.transform(background.sample(min(2000, len(background)), random_state=SEED))
        values = shap.LinearExplainer(clf, bg).shap_values(Xt)
    else:
        values = shap.TreeExplainer(clf).shap_values(Xt)
    values = np.asarray(values)
    values = values[..., 1] if values.ndim == 3 else values
    out_names = prep.get_feature_names_out()
    agg = np.zeros((values.shape[0], len(FEATURES)))
    for j, col in enumerate(out_names):
        block, rest = col.split("__", 1)
        feat = rest if block == "num" else next(c for c in CATEGORICAL if rest == c or rest.startswith(c + "_"))
        agg[:, FEATURES.index(feat)] += values[:, j]
    return agg


def top_reasons(values: np.ndarray, X: pd.DataFrame, k: int = 3) -> list[str]:
    """Top-k features pushing each order TOWARD late, in readable form."""
    out = []
    for i in range(values.shape[0]):
        idx = [j for j in np.argsort(-values[i]) if values[i, j] > 0][:k]
        out.append("; ".join(f"{FEATURES[j]}={_fmt(X.iloc[i][FEATURES[j]])}" for j in idx))
    return out


def _fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        return "n/a" if np.isnan(v) else f"{v:.3g}"
    return str(v)


# ------------------------------------------------------------------ backtest

def backtest(df: pd.DataFrame, months: list[str], model_names: list[str]) -> pd.DataFrame:
    """Out-of-sample probabilities for every order purchased in `months`,
    one column per model plus the two baselines."""
    parts = []
    for m in months:
        cutoff = pd.Timestamp(f"{m}-01")
        known = known_before(df, cutoff)
        prior = float(known["is_late"].mean())
        known = add_history_rates(known, prior)
        target = add_history_rates(df[df["month"] == m], prior)
        out = target[["order_id", "month", "is_late"]].copy()
        out["Baseline: platform rate"] = prior
        out["Baseline: seller history"] = target["seller_late_rate_hist"].to_numpy()
        for name in model_names:
            _, cal = fit_calibrated(name, known, cutoff)
            out[name] = cal.predict_proba(target[FEATURES])[:, 1]
        parts.append(out)
    return pd.concat(parts, ignore_index=True)


def summarise(oof: pd.DataFrame, scorers: list[str], thresholds: dict) -> dict:
    res = {}
    for name in scorers:
        pooled = evaluate(oof["is_late"], oof[name], thresholds.get(name, 0.5))
        monthly = {m: evaluate(g["is_late"], g[name], thresholds.get(name, 0.5))
                   for m, g in oof.groupby("month")}
        res[name] = {"pooled": pooled,
                     "monthly": monthly,
                     "roc_auc_monthly_mean": float(np.nanmean([v["roc_auc"] for v in monthly.values()])),
                     "precision_top10_monthly_mean": float(np.mean([v["precision_top10"] for v in monthly.values()])),
                     "recall_top10_monthly_mean": float(np.mean([v["recall_top10"] for v in monthly.values()])),
                     "late_rate_monthly_mean": float(np.mean([v["late_rate"] for v in monthly.values()])),
                     "pr_auc_monthly_mean": float(np.nanmean([v["pr_auc"] for v in monthly.values()])),
                     "pr_auc_monthly_min": float(np.nanmin([v["pr_auc"] for v in monthly.values()])),
                     "pr_auc_monthly_max": float(np.nanmax([v["pr_auc"] for v in monthly.values()]))}
    return res


# ------------------------------------------------------------------ run

def run(con: duckdb.DuckDBPyConnection, settings: Settings) -> dict:
    df = load_features(con)
    scorers = ["Baseline: platform rate", "Baseline: seller history"] + MODEL_NAMES

    # 1. Model selection on Jan-Mar 2018 (also fixes each model's threshold).
    sel = backtest(df, SELECTION_MONTHS, MODEL_NAMES)
    thresholds = {n: best_f1_threshold(sel["is_late"], sel[n]) for n in scorers}
    selection = summarise(sel, scorers, thresholds)
    # Selection metric: mean within-month PR-AUC - the operational question is
    # "which of this month's orders should we watch?"
    best = max(MODEL_NAMES, key=lambda n: selection[n]["pr_auc_monthly_mean"])

    # 2. Reported results on Apr-Aug 2018, thresholds frozen from selection.
    rep = backtest(df, REPORT_MONTHS, MODEL_NAMES)
    report = summarise(rep, scorers, thresholds)

    # 3. Dashboard predictions: every 2018 order, out-of-sample, best model.
    oof = pd.concat([sel, rep], ignore_index=True)[["order_id", "month", "is_late", best]] \
        .rename(columns={best: "p_late"})

    # 4. SHAP explanations for the selected model, trained on data known
    #    before April 2018 and applied to Apr-Aug orders (the information
    #    boundary of the first reported month).
    cutoff = pd.Timestamp(f"{REPORT_MONTHS[0]}-01")
    known = known_before(df, cutoff)
    prior = float(known["is_late"].mean())
    known = add_history_rates(known, prior)
    explain_model = build_model(best).fit(known[FEATURES], known["is_late"])
    report_rows = add_history_rates(df[df["month"].isin(REPORT_MONTHS)], prior).reset_index(drop=True)
    sv = shap_matrix(explain_model, report_rows[FEATURES], known[FEATURES])
    importance = pd.DataFrame({"feature": FEATURES, "mean_abs_shap": np.abs(sv).mean(axis=0)})         .sort_values("mean_abs_shap", ascending=False)
    reasons = pd.DataFrame({"order_id": report_rows["order_id"], "top_reasons": top_reasons(sv, report_rows)})

    # 5. Final model for live scoring (API / simulator): all labels known by
    #    the end of the analysis window.
    final_cutoff = pd.Timestamp("2018-09-01")
    final_known = known_before(df, final_cutoff)
    final_prior = float(final_known["is_late"].mean())
    _, final_cal = fit_calibrated(best, add_history_rates(final_known, final_prior), final_cutoff)

    # ----------------------------------------------------------- persist
    ctx = df[["order_id", "purchase_ts", "seller_key", "customer_state", "seller_state",
              "main_category", "items_value", "freight_value", "promised_days", "distance_km"]]
    preds = oof.merge(ctx, on="order_id", how="left").merge(reasons, on="order_id", how="left")
    preds["risk_band"] = risk_band(preds["p_late"])
    preds["value_at_risk"] = preds["p_late"] * (preds["items_value"] + preds["freight_value"])
    preds["period"] = np.where(preds["month"].isin(REPORT_MONTHS), "reported", "model selection")

    model_dir = settings.data_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(model_dir / "delay_predictions.parquet", index=False)
    joblib.dump({"model": final_cal, "model_name": best, "features": FEATURES, "numeric": NUMERIC,
                 "categorical": CATEGORICAL, "threshold": thresholds[best], "risk_bands": RISK_BANDS,
                 "prior_rate": final_prior, "prior_strength": PRIOR_STRENGTH,
                 "labels_known_before": str(final_cutoff.date())},
                model_dir / "delay_model.joblib")

    rep_best = rep[["is_late", best]]
    summary = {
        "prediction_moment": "payment approval",
        "design": "monthly walk-forward backtest; train on labels known before each month; "
                  f"sigmoid calibration on the last {CALIBRATION_DAYS} days of known data",
        "selection_months": SELECTION_MONTHS,
        "report_months": REPORT_MONTHS,
        "n_selection": int(len(sel)),
        "n_report": int(len(rep)),
        "selected_model": best,
        "thresholds": thresholds,
        "selection": {n: {k: v for k, v in selection[n].items() if k != "monthly"} for n in scorers},
        "report": {n: {k: v for k, v in report[n].items() if k != "monthly"} for n in scorers},
        "report_monthly_best": {m: {k: round(v, 4) for k, v in r.items()}
                                for m, r in report[best]["monthly"].items()},
        "feature_importance_shap": importance.head(15).round(5).to_dict(orient="records"),
        "reliability_report": reliability_table(rep_best["is_late"], rep_best[best]).round(4)
            .to_dict(orient="records"),
        "risk_bands_report": preds[preds["period"] == "reported"].groupby("risk_band")
            .agg(n=("is_late", "size"), observed_late_rate=("is_late", "mean"))
            .reindex([lbl for _, lbl in RISK_BANDS]).fillna(0).round(4).reset_index()
            .to_dict(orient="records"),
    }
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    (settings.exports_dir / "delay_model_metrics.json").write_text(
        json.dumps(summary, indent=2, default=float), encoding="utf-8")
    importance.round(5).to_csv(settings.exports_dir / "delay_model_shap_importance.csv", index=False)

    _charts(settings, rep, best, importance)
    _report(settings, summary)
    return summary


# ------------------------------------------------------------------ outputs

COLORS = {"Logistic Regression": "#eb6834", "Random Forest": "#1baf7a", "XGBoost": "#2a78d6",
          "Baseline: seller history": "#898781"}


def _charts(settings, rep, best, importance):
    settings.charts_dir.mkdir(parents=True, exist_ok=True)
    y = rep["is_late"]

    fig, ax = plt.subplots(figsize=(7, 5))
    for name, color in COLORS.items():
        prec, rec, _ = precision_recall_curve(y, rep[name])
        ax.plot(rec, prec, color=color, lw=2,
                label=f"{name} (PR-AUC {average_precision_score(y, rep[name]):.3f})")
    ax.axhline(y.mean(), color="#c3c2b7", lw=1, label=f"Late rate {y.mean():.3f}")
    ax.set(xlabel="Recall", ylabel="Precision", title="Precision-recall, Apr-Aug 2018 (out-of-sample)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(color="#e1e0d9", lw=0.6)
    fig.tight_layout()
    fig.savefig(settings.charts_dir / "delay_pr_curve.png", dpi=130)
    plt.close(fig)

    rel = reliability_table(y, rep[best])
    fig, ax = plt.subplots(figsize=(5.5, 5))
    top = max(rel["mean_predicted"].max(), rel["observed_rate"].max()) * 1.1
    ax.plot([0, top], [0, top], color="#c3c2b7", lw=1, label="Perfect calibration")
    ax.plot(rel["mean_predicted"], rel["observed_rate"], "o-", color="#2a78d6", lw=2, label=best)
    ax.set(xlabel="Mean predicted probability", ylabel="Observed late rate",
           title="Calibration by decile, Apr-Aug 2018")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(color="#e1e0d9", lw=0.6)
    fig.tight_layout()
    fig.savefig(settings.charts_dir / "delay_calibration.png", dpi=130)
    plt.close(fig)

    imp = importance.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(imp["feature"], imp["mean_abs_shap"], color="#2a78d6")
    ax.set(xlabel="Mean |SHAP value| (log-odds)", title=f"What drives predicted delay ({best})")
    ax.grid(axis="x", color="#e1e0d9", lw=0.6)
    fig.tight_layout()
    fig.savefig(settings.charts_dir / "delay_shap_importance.png", dpi=130)
    plt.close(fig)


def _table(block: dict) -> pd.DataFrame:
    """Headline columns are within-month averages (how well each month's
    orders are ranked); pooled Brier shows probability accuracy overall."""
    rows = []
    for name, r in block.items():
        rows.append({
            "model": name,
            "ROC-AUC (monthly mean)": r["roc_auc_monthly_mean"],
            "PR-AUC (monthly mean)": r["pr_auc_monthly_mean"],
            "PR-AUC monthly range": f"{r['pr_auc_monthly_min']:.3f}-{r['pr_auc_monthly_max']:.3f}",
            "precision@top10%": r["precision_top10_monthly_mean"],
            "recall@top10%": r["recall_top10_monthly_mean"],
            "Brier (pooled)": r["pooled"]["brier"],
        })
    return pd.DataFrame(rows).round(3)


def _report(settings, s):
    best = s["selected_model"]
    r = s["report"][best]
    seller = s["report"]["Baseline: seller history"]
    base = s["report"]["Baseline: platform rate"]
    lift = r["precision_top10_monthly_mean"] / r["late_rate_monthly_mean"]
    monthly = pd.DataFrame(s["report_monthly_best"]).T[["n", "late_rate", "roc_auc", "pr_auc",
                                                        "precision_top10", "recall_top10"]]
    lines = [
        "# Delivery-Delay Prediction",
        "",
        "**Question:** when an order's payment is approved, how likely is it to arrive after the "
        "date the customer was promised?",
        "",
        "## Set-up",
        "",
        "- **Prediction moment: payment approval.** Features use only what is known then: the order, "
        "its items and payment, the promised date, distance, and history built from orders "
        "*delivered before this order was placed* (seller, route, platform-wide last 30 days, seller "
        "last 90 days). Carrier handover, transit and delivery timestamps are never features.",
        "- **Monthly walk-forward backtest.** For each month, the model is trained only on orders "
        "whose outcome was known before the month began, calibrated on the most recent "
        f"{CALIBRATION_DAYS} days of that data, then scores every order placed in the month.",
        f"- **Jan-Mar 2018** ({s['n_selection']:,} orders) select the model and fix decision "
        f"thresholds. **Apr-Aug 2018** ({s['n_report']:,} orders) are the reported results.",
        "- Why not one random or fixed split: late rates move from ~6% (2017) to ~15% (Feb-Mar 2018) to "
        "~4% (mid-2018). A first attempt with one fixed split tuned the model on the worst quarter and "
        "tested it on a calm one; the walk-forward design and the recent-conditions features fix that.",
        "",
        "## Results, Apr-Aug 2018 (out-of-sample)",
        "",
        _table(s["report"]).to_markdown(index=False),
        "",
        f"Selected model: **{best}** (highest PR-AUC on Jan-Mar 2018).",
        "",
        f"- Average monthly PR-AUC **{r['pr_auc_monthly_mean']:.3f}** against "
        f"{seller['pr_auc_monthly_mean']:.3f} for the seller-history baseline and "
        f"{base['pr_auc_monthly_mean']:.3f} for a constant rate (a random score's PR-AUC equals the "
        "late rate); average monthly ROC-AUC "
        f"**{r['roc_auc_monthly_mean']:.3f}**.",
        f"- Watching the riskiest 10% of each month's orders catches **{r['recall_top10_monthly_mean']:.0%}** "
        f"of late deliveries, and **{r['precision_top10_monthly_mean']:.0%}** of watched orders are late: "
        f"{lift:.1f}x the base rate.",
        f"- Pooled Brier score {r['pooled']['brier']:.4f} vs {base['pooled']['brier']:.4f} for the "
        "constant rate. Probabilities are re-levelled on the most recent 45 days, and when conditions "
        "change sharply between months (e.g. the end of the Feb-Mar 2018 spike) they lag behind. Treat "
        "them as relative risk; the ranking is the reliable part.",
        "- Late delivery depends heavily on carrier events after payment, so this is a "
        "prioritisation tool (which orders to watch), not a yes/no oracle.",
        "",
        "![Precision-recall](charts/delay_pr_curve.png)",
        "",
        "### Month by month (selected model)",
        "",
        monthly.round(3).to_markdown(),
        "",
        "## Model selection, Jan-Mar 2018",
        "",
        _table(s["selection"]).to_markdown(index=False),
        "",
        "## Calibration (selected model, Apr-Aug 2018)",
        "",
        pd.DataFrame(s["reliability_report"]).to_markdown(index=False),
        "",
        "![Calibration](charts/delay_calibration.png)",
        "",
        "## Risk bands (calibrated probability, Apr-Aug 2018)",
        "",
        pd.DataFrame(s["risk_bands_report"]).to_markdown(index=False),
        "",
        "## What drives the predictions (SHAP)",
        "",
        f"From the selected model ({best}) trained on data known before April 2018, explaining "
        "Apr-Aug orders. Categorical features sum the contributions of their one-hot columns:",
        "",
        pd.DataFrame(s["feature_importance_shap"]).to_markdown(index=False),
        "",
        "![SHAP importance](charts/delay_shap_importance.png)",
        "",
        "Correlated features share credit: `seller_prior_orders` and `seller_prior_delivered` measure "
        "almost the same thing, so read them together rather than individually.",
        "",
        "SHAP shows what the model relies on, not causal effects. A long promised window, for "
        "example, goes with fewer late orders because Olist sets longer promises for harder routes; "
        "lengthening a promise would not by itself make deliveries faster.",
        "",
        "## Limitations",
        "",
        "- Only delivered orders are labelled; orders still in transit at the data snapshot are "
        "excluded, slightly understating late rates at the very end of the period.",
        "- Delivery outcomes are recorded per order; the largest seller represents multi-seller orders.",
        "- Explanations come from the selected model as trained before April; each later month's model "
        "is refit on more data, so its weights drift slightly from the explained one.",
    ]
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "delay_model.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(settings: Settings | None = None):
    from src.config import get_settings
    from src.db import connect

    settings = settings or get_settings()
    with connect(settings) as con:
        s = run(con, settings)
    print(f"  selected: {s['selected_model']}")
    for name, r in s["report"].items():
        print(f"  {name:<26} monthly ROC-AUC {r['roc_auc_monthly_mean']:.3f}  "
              f"PR-AUC {r['pr_auc_monthly_mean']:.3f} ({r['pr_auc_monthly_min']:.3f}-{r['pr_auc_monthly_max']:.3f})  "
              f"top10% P {r['precision_top10_monthly_mean']:.2f} R {r['recall_top10_monthly_mean']:.2f}  "
              f"Brier {r['pooled']['brier']:.4f}")


if __name__ == "__main__":
    main()
