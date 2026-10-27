"""Unit tests for the statistical helpers and analytics logic."""

import numpy as np
import pandas as pd
import pytest

from src.analytics import demand_variability as dv
from src.analytics import stats
from src.analytics.seller_scorecard import INSUFFICIENT, build_scorecard


# ---------------------------------------------------------------- stats

def test_wilson_interval_known_values():
    lo, hi = stats.wilson_interval(0, 10)
    assert lo == pytest.approx(0.0, abs=1e-12) and hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = stats.wilson_interval(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)


def test_wilson_interval_narrows_with_sample_size():
    lo_s, hi_s = stats.wilson_interval(3, 10)
    lo_l, hi_l = stats.wilson_interval(300, 1000)
    assert (hi_l - lo_l) < (hi_s - lo_s)


def test_shrinkage_pulls_small_samples_harder():
    a, b = 5.0, 95.0                      # prior mean 5%, worth 100 obs
    small = stats.shrink_proportion(1, 2, a, b)        # raw 50%
    large = stats.shrink_proportion(500, 1000, a, b)   # raw 50%
    assert small < 0.07 and large > 0.45


def test_beta_prior_recovers_population_rate():
    rng = np.random.default_rng(0)
    n = np.full(400, 200)
    k = rng.binomial(n, rng.beta(10, 90, size=400))
    a, b = stats.beta_prior_mom(k, n)
    assert a / (a + b) == pytest.approx(0.10, abs=0.01)
    assert 50 < a + b < 200               # true strength 100


def test_beta_prior_falls_back_when_no_between_variance():
    a, b = stats.beta_prior_mom([5, 5, 5], [100, 100, 100])
    assert a / (a + b) == pytest.approx(0.05)


def test_percentile_score_is_outlier_robust():
    s = pd.Series([1, 2, 3, 4, 1000])
    lin = (s - s.min()) / (s.max() - s.min()) * 100
    pct = stats.percentile_score(s)
    assert lin.iloc[3] < 1                # min-max squashes 4 next to 1
    assert pct.iloc[3] == pytest.approx(80)
    assert list(stats.percentile_score(s, higher_is_better=False)) == list(pct[::-1])


def test_quantile_tiers_shares():
    score = pd.Series(np.arange(100, dtype=float))
    tiers = stats.assign_quantile_tiers(score, [("A", .25), ("B", .50), ("C", .15), ("D", .10)])
    assert tiers.value_counts().to_dict() == {"A": 25, "B": 50, "C": 15, "D": 10}
    assert tiers.iloc[99] == "A" and tiers.iloc[0] == "D"


def test_quantile_tiers_reject_bad_shares():
    with pytest.raises(ValueError):
        stats.assign_quantile_tiers(pd.Series([1.0, 2.0]), [("A", .5), ("B", .4)])


def test_two_proportion_ztest():
    same = stats.two_proportion_ztest(50, 1000, 50, 1000)
    assert same["p_value"] == pytest.approx(1.0)
    diff = stats.two_proportion_ztest(10, 1000, 70, 1000)
    assert diff["p_value"] < 1e-6 and diff["diff"] < 0


# ---------------------------------------------------------------- demand

def test_cv_and_sbc_classification():
    assert dv.classify_cv(0.3) == "Stable"
    assert dv.classify_cv(0.8) == "Variable"
    assert dv.classify_cv(1.5) == "Highly Variable"
    assert dv.sbc_class(1.0, 0.2) == "Smooth"
    assert dv.sbc_class(1.0, 0.8) == "Erratic"
    assert dv.sbc_class(2.0, 0.2) == "Intermittent"
    assert dv.sbc_class(2.0, 0.8) == "Lumpy"


def test_zero_weeks_raise_cv_and_adi():
    weeks = pd.date_range("2017-01-02", periods=8, freq="W-MON")
    weekly = pd.DataFrame({
        "category_en": ["a"] * 8,
        "week_start": weeks,
        "n_items_sold": [10, 0, 10, 0, 10, 0, 10, 0],
        "revenue": [100.0, 0, 100, 0, 100, 0, 100, 0],
    })
    summary = dv.summarise(dv.add_z_scores(weekly)).iloc[0]
    assert summary["mean_weekly_demand"] == 5
    assert summary["adi"] == 2.0
    assert summary["zero_week_share"] == 0.5
    # active-weeks-only (the v1 method) would give CV = 0
    assert summary["coefficient_of_variation"] == pytest.approx(np.std([10, 0] * 4, ddof=1) / 5)


# ---------------------------------------------------------------- sellers

def _raw_sellers():
    rows = []
    for i in range(40):
        rows.append({"seller_id": f"big{i}", "state": "SP", "region": "Southeast",
                     "n_orders": 100, "n_items": 120, "total_revenue": 1e4,
                     "n_delivered": 100, "n_late": 5 + (i % 5), "n_canceled": 1,
                     "n_with_handover": 100, "n_missed_shipping_limit": 3,
                     "avg_fulfilment_days": 2 + i / 20, "avg_review_score": 4.2,
                     "n_reviews": 95, "freight_to_price_pct": 15.0})
    rows.append({**rows[0], "seller_id": "bad", "n_late": 40, "avg_review_score": 2.5})
    rows.append({**rows[0], "seller_id": "tiny", "n_orders": 3, "n_delivered": 3, "n_late": 3,
                 "n_reviews": 3, "avg_review_score": 1.0})
    return pd.DataFrame(rows)


def _reviews(raw):
    return pd.DataFrame({"seller_id": np.repeat(raw["seller_id"], 3),
                         "review_score": np.tile([3, 4, 5], len(raw))})


def test_scorecard_excludes_small_sellers_from_ranking():
    raw = _raw_sellers()
    df, params = build_scorecard(raw, _reviews(raw), min_orders=30)
    tiny = df.set_index("seller_id").loc["tiny"]
    assert tiny["performance_tier"] == INSUFFICIENT and pd.isna(tiny["seller_score"])
    assert params["n_scored"] == 41


def test_scorecard_flags_significantly_late_seller():
    raw = _raw_sellers()
    df, _ = build_scorecard(raw, _reviews(raw), min_orders=30)
    by_id = df.set_index("seller_id")
    assert bool(by_id.loc["bad", "late_rate_flag"]) is True
    assert by_id.loc["bad", "performance_tier"] in {"Critical", "At Risk"}
    assert not by_id.drop(index=["bad", "tiny"])["late_rate_flag"].any()
    # shrinkage: the tiny seller's 100% raw late rate is pulled far down
    assert by_id.loc["tiny", "late_rate_adj"] < 0.5
