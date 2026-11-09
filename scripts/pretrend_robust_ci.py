"""
Robust confidence intervals for the average post-period effect under the smoothness restriction Delta^SD(M) (Rambachan and Roth 2023).

Implements a fixed-length confidence interval (FLCI) in the spirit of Armstrong and Kolesar / Rambachan-Roth: choose an affine estimator
theta_hat = l'b_post - w'b_pre, whose worst-case bias over Delta^SD(M) is b_max(w) (a linear program) and whose standard error is se(w);
the interval is theta_hat +/- cv(b_max/se) * se, with cv the (1-alpha) quantile of |N(b_max/se, 1)|; w minimises the half-length.
Event study: quarter x treated coefficients (reference quarter 2024Q3 = -1, quarters clipped to [-8, 6]), covariance clustered by month.
Writes results/pretrend_robust_ci.json
"""
import json
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from scipy.optimize import linprog, minimize
from scipy.stats import norm, ncx2
from src import config

m = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet")
m["t"] = m.ym.dt.to_timestamp()
m = m[(m.t >= "2023-01-01") & (m.t < "2026-10-01") & (m.ym != pd.Period("2024-11")) & (m.tot > 0) & (m.exp_day > 0)].copy()
m["lt"], m["ls"], m["le"] = np.log(m.tot), np.log(m.share), np.log(m.exp_day)
m["q"] = ((m.t.dt.year - 2024) * 4 + (m.t.dt.quarter - 4)).clip(-8, 6)
m["mon"] = m.ym.astype(str)
ALPHA = 0.05


def event_study(tr, ct, y):
    d = m[m.Symbol.isin([tr, ct])].copy(); d["bn"] = (d.Symbol == tr).astype(int)
    r = smf.ols(f"{y} ~ C(q, Treatment(-1)):bn + C(q) + bn", d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.mon)[0]})
    keys = {}
    for k in r.params.index:
        if ":bn" in k:
            keys[int(float(k.split("[T.")[1].split("]")[0]))] = k
    qs = sorted(keys); pre = [q for q in qs if q < 0]; post = [q for q in qs if q >= 0]
    b = np.array([r.params[keys[q]] for q in pre + post]); S = r.cov_params().loc[[keys[q] for q in pre + post], [keys[q] for q in pre + post]].values
    return pre, post, b, S


def sd_constraints(pre, post, M):
    """delta over (pre..., [reference=0 at -1 inserted], post...): variables are all non-reference periods; |second difference| <= M for every triple."""
    periods = sorted(pre + [-1] + post); idx = {q: i for i, q in enumerate([q for q in periods if q != -1])}
    A, b = [], []
    for i in range(1, len(periods) - 1):
        row = np.zeros(len(idx))
        for j, c in zip((i - 1, i, i + 1), (1.0, -2.0, 1.0)):
            q = periods[j]
            if q != -1: row[idx[q]] += c
        A += [row, -row]; b += [M, M]
    return np.array(A), np.array(b), idx


def max_bias(w, pre, post, M, A, bvec, idx):
    n_post = len(post)
    c = np.zeros(len(idx))
    for q in post: c[idx[q]] += 1.0 / n_post
    for k, q in enumerate(pre): c[idx[q]] -= w[k]
    res = linprog(-c, A_ub=A, b_ub=bvec, bounds=[(None, None)] * len(idx))
    return -res.fun if res.status == 0 else np.inf


def cv(ratio):
    return np.sqrt(ncx2.ppf(1 - ALPHA, 1, ratio ** 2))


def flci(pre, post, b, S, M):
    n_pre, n_post = len(pre), len(post)
    A, bvec, idx = sd_constraints(pre, post, M)
    l = np.r_[-np.zeros(n_pre), np.ones(n_post) / n_post]

    def half(w):
        a = np.r_[-w, np.ones(n_post) / n_post]
        se = float(np.sqrt(a @ S @ a)); bias = max_bias(w, pre, post, M, A, bvec, idx)
        return cv(bias / se) * se if np.isfinite(bias) else 1e9

    # weights must cancel any linear differential trend (allowed under Delta^SD): sum_k w_k (q_k + 1) = mean_post(q + 1)
    r = np.array([q + 1.0 for q in pre]); target = float(np.mean([q + 1.0 for q in post]))
    w0 = r * target / float(r @ r)
    U, _, Vt = np.linalg.svd(r.reshape(1, -1)); Z = Vt[1:].T                      # null space of the constraint
    wf = lambda z: w0 + Z @ z
    half_z = lambda z: half(wf(z))
    best = None
    for k in range(4):
        z0 = np.zeros(Z.shape[1]) if k == 0 else np.random.default_rng(k).normal(0, 0.2, Z.shape[1])
        r_ = minimize(half_z, z0, method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-7, "maxiter": 3000})
        if best is None or r_.fun < best.fun: best = r_
    best.x = wf(best.x)
    w = best.x; a = np.r_[-w, np.ones(n_post) / n_post]
    est = float(a @ b); h = float(best.fun)
    return est, est - h, est + h


out = {}
for lab, (tr, ct) in {"NSE: BANKNIFTY vs NIFTY": ("BANKNIFTY", "NIFTY"), "BSE: BANKEX vs SENSEX": ("BANKEX", "SENSEX")}.items():
    out[lab] = {}
    for y in ["ls", "lt", "le"]:
        pre, post, b, S = event_study(tr, ct, y)
        pre_path = np.r_[b[:len(pre)], 0.0]
        d2 = np.abs(np.diff(pre_path, 2)); Mpre = float(d2.max())
        naive = float(b[len(pre):].mean()); se_naive = float(np.sqrt((np.r_[np.zeros(len(pre)), np.ones(len(post)) / len(post)]) @ S @ (np.r_[np.zeros(len(pre)), np.ones(len(post)) / len(post)])))
        res = {"theta_naive": naive, "se_naive": se_naive, "naive_ci": [naive - 1.96 * se_naive, naive + 1.96 * se_naive], "M_pre": Mpre, "flci": {}}
        for mult in [0, 0.5, 1, 2]:
            e, lo, hi = flci(pre, post, b, S, mult * Mpre)
            res["flci"][f"{mult}xM_pre"] = {"estimate": e, "lo": lo, "hi": hi}
        star = None; prev = 0.0
        for mult in [0, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4]:
            e, lo, hi = flci(pre, post, b, S, mult * Mpre)
            if lo <= 0 <= hi: star = mult; break
            prev = mult
        if star is not None and star > prev and lab.startswith("NSE"):      # bisection for the breakdown multiple (NSE pair)
            lo_m, hi_m = prev, star
            for _ in range(5):
                mid = (lo_m + hi_m) / 2; e, lo, hi = flci(pre, post, b, S, mid * Mpre)
                if lo <= 0 <= hi: hi_m = mid
                else: lo_m = mid
            star = hi_m
        res["breakdown_multiple_of_M_pre_ci"] = star
        out[lab][y] = res
        f = res["flci"]
        print(f"{lab:26s} {y}: naive {naive:+.2f} [{res['naive_ci'][0]:+.2f},{res['naive_ci'][1]:+.2f}] | M=0 [{f['0xM_pre']['lo']:+.2f},{f['0xM_pre']['hi']:+.2f}] "
              f"M=1xMpre [{f['1xM_pre']['lo']:+.2f},{f['1xM_pre']['hi']:+.2f}] | CI breakdown (x M_pre): {star}", flush=True)
json.dump(out, open(config.RESULTS_DIR / "pretrend_robust_ci.json", "w"), indent=1)
