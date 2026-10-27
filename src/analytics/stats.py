"""
Small, tested statistical helpers shared by the analytics modules.

The theme: never rank or compare groups on raw rates without accounting for
how many observations sit behind each rate.
"""

import math

import numpy as np
import pandas as pd
from scipy import stats


def wilson_interval(successes, trials, z: float = 1.96):
    """95% Wilson score interval for a binomial proportion. Vectorised;
    returns (lower, upper) as fractions. Well-behaved for small n and for
    proportions near 0 or 1, unlike the normal approximation."""
    k = np.asarray(successes, dtype=float)
    n = np.asarray(trials, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = k / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def beta_prior_mom(successes, trials) -> tuple[float, float]:
    """Method-of-moments fit of a Beta(alpha, beta) prior to a set of group
    proportions (empirical Bayes). Falls back to a weak prior centred on the
    pooled rate if the between-group variance is not identifiable."""
    k = np.asarray(successes, dtype=float)
    n = np.asarray(trials, dtype=float)
    pooled = k.sum() / n.sum()
    p = k / n
    mean = np.average(p, weights=n)
    var = np.average((p - mean) ** 2, weights=n)
    # subtract the expected binomial sampling variance to get the true spread
    sampling_var = np.mean(mean * (1 - mean) / n)
    between = var - sampling_var
    if between <= 0 or mean in (0, 1):
        strength = 10.0
        return pooled * strength, (1 - pooled) * strength
    strength = mean * (1 - mean) / between - 1
    strength = float(np.clip(strength, 1.0, 1e4))
    return mean * strength, (1 - mean) * strength


def shrink_proportion(successes, trials, alpha: float, beta: float):
    """Posterior mean under a Beta(alpha, beta) prior: pulls small-sample
    rates toward the population rate, large-sample rates barely move."""
    k = np.asarray(successes, dtype=float)
    n = np.asarray(trials, dtype=float)
    return (k + alpha) / (n + alpha + beta)


def shrink_mean(group_means, group_ns, global_mean: float, prior_strength: float):
    """Shrinks group means toward the global mean with `prior_strength`
    pseudo-observations (normal-normal empirical Bayes)."""
    m = np.asarray(group_means, dtype=float)
    n = np.asarray(group_ns, dtype=float)
    return (n * m + prior_strength * global_mean) / (n + prior_strength)


def mean_prior_strength(values: pd.Series, groups: pd.Series) -> float:
    """Ratio of within-group variance to between-group variance of the
    group means: the number of observations at which a group's own mean is
    trusted as much as the population mean."""
    df = pd.DataFrame({"v": values, "g": groups}).dropna()
    g = df.groupby("g")["v"].agg(["mean", "var", "count"])
    within = np.average(g["var"].fillna(0), weights=g["count"])
    between = g["mean"].var() - np.mean(within / g["count"])
    if not np.isfinite(between) or between <= 0:
        return 10.0
    return float(np.clip(within / between, 1.0, 1e4))


def percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """0-100 percentile rank. Unlike min-max scaling, a single extreme
    outlier cannot compress everyone else into a narrow band."""
    oriented = series if higher_is_better else -series
    return oriented.rank(pct=True, method="average") * 100


def two_proportion_ztest(k1: int, n1: int, k2: int, n2: int) -> dict:
    """Two-sided pooled z-test for p1 != p2."""
    p1, p2 = k1 / n1, k2 / n2
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se if se > 0 else 0.0
    p_value = math.erfc(abs(z) / math.sqrt(2))
    return {"p1": p1, "p2": p2, "diff": p1 - p2, "z": z, "p_value": p_value}


def mann_whitney(a, b) -> dict:
    """Two-sided Mann-Whitney U for ordinal outcomes such as 1-5 review scores."""
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"u": float(res.statistic), "p_value": float(res.pvalue)}


def assign_quantile_tiers(score: pd.Series, tiers: list[tuple[str, float]]) -> pd.Series:
    """Assigns tiers from the TOP of the distribution down. `tiers` is a list
    of (label, share) whose shares sum to 1, e.g.
    [("Excellent", .25), ("Good", .50), ("At Risk", .15), ("Critical", .10)].
    Tiers are explicitly relative: they rank, they do not certify."""
    if not math.isclose(sum(s for _, s in tiers), 1.0):
        raise ValueError("tier shares must sum to 1")
    pct_from_top = 1 - score.rank(pct=True, method="first") + 1 / len(score)
    edges = np.cumsum([s for _, s in tiers])
    labels = [l for l, _ in tiers]
    idx = np.searchsorted(edges, pct_from_top.to_numpy() - 1e-12, side="left")
    return pd.Series([labels[min(i, len(labels) - 1)] for i in idx], index=score.index)
