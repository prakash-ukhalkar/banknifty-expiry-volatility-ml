"""
Corrected DiD on a symbol-month panel built from TRUE per-index expiry dates
(scripts/build_index_expiry_panel.py). Unit = symbol-month, so the 23 post-reform
expiry events are not inflated into thousands of daily rows. Nov-2024 (transition
month) is dropped. Outcomes (logs): total F&O turnover, monthly-expiry-day
turnover, and expiry-day share of the month's turnover.
Treated: BANKNIFTY (and, pooled, FINNIFTY/MIDCPNIFTY); control: NIFTY.
Caveat reported with results: NIFTY is not a clean control (it absorbed displaced activity).
"""
import json
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from src import config

m = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel.parquet")
m["t"] = m["ym"].dt.to_timestamp()
m = m[(m["exp_day"] > 0) & (m["tot"] > 0) & (m["ym"] != pd.Period("2024-11"))].copy()
m["post"] = (m["t"] >= "2024-12-01").astype(int)
m["lt"], m["le"], m["ls"] = np.log(m.tot), np.log(m.exp_day), np.log(m.share)
m["trend"] = (m["t"] - m["t"].min()).dt.days / 365.25
out = {}

def did(df, y, label):
    df = df.copy()
    df["treated"] = (df.Symbol != "NIFTY").astype(int)
    r = smf.ols(f"{y} ~ treated*post + trend + treated:trend + C(Symbol)", df).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(df.t)[0]})
    k = "treated:post"
    out[f"{label}|{y}"] = {"coef": r.params[k], "se": r.bse[k], "p": r.pvalues[k], "n": int(r.nobs)}
    print(f"{label:22s} {y}: {r.params[k]:+.3f} (se {r.bse[k]:.3f}) pct={np.expm1(r.params[k])*100:+.0f}%")

for lab, syms in [("BN vs NIFTY", ["BANKNIFTY", "NIFTY"]),
                  ("BN+FIN+MIDCP vs NIFTY", ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTY"])]:
    d = m[m.Symbol.isin(syms)]
    for y in ["lt", "le", "ls"]:
        did(d, y, lab)

# event study (quarters rel. to 2024Q4), BN vs NIFTY, outcome = log expiry-day share
d = m[m.Symbol.isin(["BANKNIFTY", "NIFTY"])].copy()
d["bn"] = (d.Symbol == "BANKNIFTY").astype(int)
d["q"] = ((d.t.dt.year - 2024) * 4 + (d.t.dt.quarter - 4)).clip(-8, 6)
for y in ["ls", "lt"]:
    r = smf.ols(f"{y} ~ C(q, Treatment(-1)):bn + C(q) + bn", d).fit(cov_type="HC1")
    es = {k.split("[T.")[1].split("]")[0]: (r.params[k], r.pvalues[k]) for k in r.params.index if ":bn" in k}
    out[f"eventstudy|{y}"] = es
    print(y, {k: (round(v[0], 2), round(v[1], 3)) for k, v in sorted(es.items(), key=lambda kv: float(kv[0]))})
json.dump(out, open(config.RESULTS_DIR / "did_monthly_true_expiry.json", "w"), indent=1, default=float)
