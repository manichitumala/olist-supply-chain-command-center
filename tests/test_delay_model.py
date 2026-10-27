"""Tests for the delay-prediction features and model code.

The most important ones guard against leakage: a feature computed at
payment approval must never see an outcome that happened later."""

import json

import numpy as np
import pandas as pd
import pytest

from src.config import ROOT
from src.models import delay_prediction as dp


@pytest.fixture(scope="module")
def features(synthetic_warehouse):
    return dp.load_features(synthetic_warehouse).set_index("order_id")


def test_population_is_delivered_orders_in_window(features):
    # o_missing has no delivered date and is outside the window; cancelled /
    # unavailable orders are never delivered.
    assert set(features.index) == {"o_due_day", "o_late_3", "o_multi"}
    assert features.loc["o_late_3", "is_late"] == 1
    assert features.loc["o_due_day", "is_late"] == 0


def test_seller_history_only_counts_earlier_deliveries(features):
    # s1: o_due_day purchased 03-01, delivered 03-10 (on time).
    assert features.loc["o_due_day", ["seller_prior_delivered", "seller_prior_late"]].tolist() == [0, 0]
    # o_late_3 purchased 04-01 sees exactly one earlier delivery for s1.
    assert features.loc["o_late_3", ["seller_prior_delivered", "seller_prior_late"]].tolist() == [1, 0]


def test_own_outcome_never_in_history(features):
    # o_late_3 is late, but its own lateness must not appear in its history.
    assert features.loc["o_late_3", "seller_prior_late"] == 0


def test_primary_seller_is_largest_item_value(features):
    # o_multi: s1 sells 30.00, s2 sells 40.00 -> s2 represents the order,
    # and s2 has no earlier delivered orders.
    assert features.loc["o_multi", "seller_key"] == "s2"
    assert features.loc["o_multi", "seller_prior_delivered"] == 0


def test_route_history_is_point_in_time(features):
    # Route SP>SP: o_due_day delivered before o_late_3 was purchased.
    assert features.loc["o_late_3", "route_prior_delivered"] == 1
    assert features.loc["o_due_day", "route_prior_delivered"] == 0


def test_no_post_approval_columns_are_features():
    forbidden = {"delivered_ts", "carrier_ts", "transit_time_hours", "fulfilment_time_hours",
                 "lead_time_days", "days_late", "review_score", "otd_status", "is_late"}
    assert not forbidden & set(dp.FEATURES)


def test_known_before_uses_delivery_time_not_purchase_time():
    df = pd.DataFrame({"delivered_ts": pd.to_datetime(["2018-03-20", "2018-04-02"]),
                       "purchase_ts": pd.to_datetime(["2018-03-01", "2018-03-05"])})
    known = dp.known_before(df, pd.Timestamp("2018-04-01"))
    # The second order was PURCHASED in March but its outcome was unknown on 1 April.
    assert len(known) == 1


def test_history_prior_comes_from_argument():
    df = pd.DataFrame({"seller_prior_late": [0], "seller_prior_delivered": [0],
                       "route_prior_late": [0], "route_prior_delivered": [0],
                       "seller_late_90d": [0], "seller_delivered_90d": [0],
                       "platform_late_30d": [0], "platform_delivered_30d": [0]})
    out = dp.add_history_rates(df, prior_rate=0.2)
    assert out.loc[0, "seller_late_rate_hist"] == pytest.approx(0.2)
    assert out.loc[0, "platform_late_rate_30d"] == pytest.approx(0.2)


def test_evaluate_top10_and_threshold():
    y = np.array([1] * 10 + [0] * 90)
    p = np.linspace(1, 0, 100)                 # perfect ranking
    m = dp.evaluate(y, p, threshold=dp.best_f1_threshold(y, p))
    assert m["roc_auc"] == pytest.approx(1.0)
    assert m["precision_top10"] == pytest.approx(1.0)
    assert m["recall_top10"] == pytest.approx(1.0)
    assert m["f1"] == pytest.approx(1.0)


def test_risk_bands():
    assert list(dp.risk_band([0.05, 0.10, 0.3, 0.9])) == ["Low", "Medium", "High", "Critical"]


def _random_frame(n=400, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({c: rng.normal(size=n) for c in dp.NUMERIC})
    df["customer_state"] = rng.choice(["SP", "RJ", "MG"], n)
    df["seller_state"] = rng.choice(["SP", "PR"], n)
    df["main_category"] = rng.choice(["a", "b"], n)
    df["payment_type"] = rng.choice(["credit_card", "boleto"], n)
    y = (df["promised_days"] + (df["customer_state"] == "RJ") + rng.normal(size=n) > 1.5).astype(int)
    return df, y


@pytest.mark.parametrize("name", dp.MODEL_NAMES)
def test_shap_matrix_has_one_column_per_original_feature(name):
    X, y = _random_frame()
    model = dp.build_model(name).fit(X[dp.FEATURES], y)
    sv = dp.shap_matrix(model, X[dp.FEATURES].head(50), X[dp.FEATURES])
    assert sv.shape == (50, len(dp.FEATURES))
    assert np.isfinite(sv).all()


def test_linear_shap_sums_to_logit_difference():
    X, y = _random_frame()
    model = dp.build_model("Logistic Regression").fit(X[dp.FEATURES], y)
    sv = dp.shap_matrix(model, X[dp.FEATURES].head(20), X[dp.FEATURES])
    logits = model.decision_function(X[dp.FEATURES].head(20))
    # Additivity: contributions differ from the logit only by a constant base value.
    assert np.ptp(logits - sv.sum(axis=1)) < 1e-6


def test_real_model_beats_baselines(real_warehouse):
    path = ROOT / "data" / "exports" / "delay_model_metrics.json"
    if not path.exists():
        pytest.skip("delay model not trained")
    s = json.loads(path.read_text(encoding="utf-8"))
    best = s["report"][s["selected_model"]]
    assert best["pr_auc_monthly_mean"] > 2 * s["report"]["Baseline: platform rate"]["pr_auc_monthly_mean"]
    assert best["roc_auc_monthly_mean"] > s["report"]["Baseline: seller history"]["roc_auc_monthly_mean"]
    assert s["selection_months"][-1] < s["report_months"][0]
