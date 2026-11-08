"""
Pre-trend sensitivity for the quarterly event studies (Rambachan-Roth 2023 smoothness restriction, "Delta^SD(M)").
Event study: y_{s,t} = quarter FE + symbol FE + sum_q beta_q 1[q] x treated, reference quarter q=-1 (2024Q3), q clipped to [-8, 6].
Pre-period coefficients are taken as pure differential trend (delta_q = beta_q for q <= -2, delta_-1 = 0). For post quarters q = 0..6 the
differential trend delta_q is unknown; we restrict its second differences: |delta_{t+1} - 2 delta_t + delta_{t-1}| <= M for every triple that
touches a post period.  The parameter is theta = mean_{q>=0}(beta_q - delta_q).  Identified set = [theta_lo, theta_hi] by linear programming.
The pre-period "roughness" is M_pre = max |second difference| of the estimated pre path.  The breakdown value M* is the smallest M for
which 0 enters the identified set, reported as a multiple of M_pre.
NOTE: identified set at point estimates (sampling error ignored); inference-robust version (Rambachan-Roth FLCI / C-LF) is NOT implemented.
Writes results/pretrend_sensitivity.json
"""
import json
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from scipy.optimize import linprog
from src import config

m = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet")
m["t"] = m.ym.dt.to_timestamp()
m = m[(m.t >= "2023-01-01") & (m.t < "2026-10-01") & (m.ym != pd.Period("2024-11")) & (m.tot > 0) & (m.exp_day > 0)].copy()
m["lt"], m["ls"], m["le"] = np.log(m.tot), np.log(m.share), np.log(m.exp_day)
m["q"] = ((m.t.dt.year - 2024) * 4 + (m.t.dt.quarter - 4)).clip(-8, 6)


def event_study(tr, ct, y):
    d = m[m.Symbol.isin([tr, ct])].copy(); d["bn"] = (d.Symbol == tr).astype(int)
    r = smf.ols(f"{y} ~ C(q, Treatment(-1)):bn + C(q) + bn", d).fit(cov_type="HC1")
    b = {}
    for k in r.params.index:
        if ":bn" in k:
            b[int(float(k.split("[T.")[1].split("]")[0]))] = float(r.params[k])
    b[-1] = 0.0
    return dict(sorted(b.items())), r


def bounds(beta, M):
    qs = sorted(beta); pre = [q for q in qs if q <= -1]; post = [q for q in qs if q >= 0]
    n = len(post); full = pre + post
    A, b = [], []
    for i in range(1, len(full) - 1):
        if full[i + 1] < 0:           # triple entirely in the (known) pre-period
            continue
        row = np.zeros(n); const = 0.0
        for j, c in zip((i - 1, i, i + 1), (1.0, -2.0, 1.0)):
            q = full[j]
            if q >= 0: row[post.index(q)] += c
            else: const += c * (beta[q])  # known pre delta (= beta, ref = 0)
        A += [row, -row]; b += [M - const, M + const]
    mb = np.mean([beta[q] for q in post])
    A, b = np.array(A), np.array(b)
    one = np.ones(n) / n
    mx = linprog(-one, A_ub=A, b_ub=b, bounds=[(None, None)] * n)   # maximise mean(delta_post)
    mn = linprog(one, A_ub=A, b_ub=b, bounds=[(None, None)] * n)    # minimise mean(delta_post)
    if mx.status != 0 or mn.status != 0:
        return None
    return mb - (-mx.fun), mb - mn.fun                                # [theta_lo, theta_hi] = mean(beta) - mean(delta)


out = {}
for lab, (tr, ct) in {"NSE: BANKNIFTY vs NIFTY": ("BANKNIFTY", "NIFTY"), "BSE: BANKEX vs SENSEX": ("BANKEX", "SENSEX")}.items():
    out[lab] = {}
    for y in ["ls", "lt", "le"]:
        beta, r = event_study(tr, ct, y)
        pre = [beta[q] for q in sorted(beta) if q <= -1]
        d2 = np.abs(np.diff(pre, 2)); Mpre = float(d2.max()) if len(d2) else float("nan")
        theta = float(np.mean([beta[q] for q in beta if q >= 0]))
        res = {"theta_naive": theta, "M_pre": Mpre, "bounds": {}}
        for mult in [0, 0.5, 1, 2, 4]:
            bd = bounds(beta, mult * Mpre)
            res["bounds"][f"{mult}xM_pre"] = None if bd is None else [float(bd[0]), float(bd[1])]
        # breakdown multiple
        sign = np.sign(theta); star = None
        for mult in np.arange(0, 60.01, 0.05):
            bd = bounds(beta, mult * Mpre)
            if bd is None: continue
            if bd[0] <= 0 <= bd[1]: star = float(mult); break
        res["breakdown_multiple_of_M_pre"] = star
        res["grid"] = [[float(k), *map(float, bounds(beta, k * Mpre))] for k in np.arange(0, 3.01, 0.1) if bounds(beta, k * Mpre) is not None]
        out[lab][y] = res
        print(f"{lab:26s} {y}: theta={theta:+.2f} M_pre={Mpre:.3f} bounds@1x={res['bounds']['1xM_pre']} breakdown={star}")
json.dump(out, open(config.RESULTS_DIR / "pretrend_sensitivity.json", "w"), indent=1)
