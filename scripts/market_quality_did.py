"""
Market-quality outcomes for the near-month index futures of the six indices, then the same within-exchange DiDs as
scripts/cross_exchange_did.py (BANKNIFTY vs NIFTY on NSE; BANKEX vs SENSEX on BSE) plus pooled two-way FE with
randomization inference.  Daily measures -> monthly means.
  amihud     = |close-to-close return| / traded value (INR trillion)          [price impact per rupee traded]
  cs_spread  = Corwin-Schultz (2012) two-day high-low spread estimator (negative -> 0)
  hl_range   = log(High/Low) of the near-month future (intraday range)
  zero_days  = share of days with zero traded value in the near-month future
Expiry-day observations of the near-month contract are excluded (the contract is settling that day).
Caveat: futures are the liquid hedging instrument, not the delisted options, so these are SPILLOVER outcomes.
Writes results/market_quality_did.json
"""
import itertools, json
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from src import config

f = pd.read_parquet(config.INTERIM_DATA_DIR / "futures_daily.parquet").sort_values(["Symbol", "Date"]).reset_index(drop=True)
f = f[(f.Expiry > f.Date) & (f.H > 0) & (f.L > 0) & (f.C > 0)].copy()
f["ret"] = f.groupby(["Symbol", "Expiry"]).C.transform(lambda s: np.log(s).diff())   # same-contract returns only
f["amihud"] = f.ret.abs() / (f.Value / 1e12).replace(0, np.nan)
f["hl"] = np.log(f.H / f.L)
def cs(g):
    b = (np.log(g.H / g.L)) ** 2; b2 = b + b.shift(1)
    hh = np.log(np.maximum(g.H, g.H.shift(1)) / np.minimum(g.L, g.L.shift(1))) ** 2
    beta = b2; gamma = hh
    alpha = (np.sqrt(2 * b.shift(0)) - np.sqrt(b)) / (3 - 2 * np.sqrt(2)) - np.sqrt(gamma / (3 - 2 * np.sqrt(2)))
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return s.clip(lower=0)
# Corwin-Schultz with standard definitions
def cs_spread(g):
    hl2 = np.log(g.H / g.L) ** 2
    beta = hl2 + hl2.shift(1)
    H2 = np.maximum(g.H, g.H.shift(1)); L2 = np.minimum(g.L, g.L.shift(1))
    gamma = np.log(H2 / L2) ** 2
    k = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return s.clip(lower=0)
f["cs_spread"] = f.groupby(["Symbol", "Expiry"], group_keys=False).apply(cs_spread)
f["zero"] = (f.Value <= 0).astype(float)
f["ym"] = f.Date.dt.to_period("M")
mq = f.groupby(["Symbol", "ym"]).agg(amihud=("amihud", "median"), cs_spread=("cs_spread", "mean"), hl=("hl", "mean"),
                                     zero_days=("zero", "mean"), n=("C", "size")).reset_index()
mq["t"] = mq.ym.dt.to_timestamp()
mq = mq[(mq.t >= "2023-06-01") & (mq.t < "2026-10-01") & (mq.ym != pd.Period("2024-11")) & (mq.n >= 8)].copy()
mq["post"] = (mq.t >= "2024-12-01").astype(int); mq["trend"] = (mq.t - pd.Timestamp("2023-06-01")).dt.days / 365.25
mq["l_amihud"] = np.log(mq.amihud.clip(lower=1e-9)); mq["l_hl"] = np.log(mq.hl.clip(lower=1e-9))
mq.to_parquet(config.INTERIM_DATA_DIR / "market_quality_monthly.parquet", index=False)
out = {}
for lab, (tr, ct) in {"NSE: BANKNIFTY vs NIFTY": ("BANKNIFTY", "NIFTY"), "BSE: BANKEX vs SENSEX": ("BANKEX", "SENSEX")}.items():
    d = mq[mq.Symbol.isin([tr, ct])].copy(); d["tr"] = (d.Symbol == tr).astype(int); out[lab] = {}
    for y in ["l_amihud", "cs_spread", "l_hl", "zero_days"]:
        dd = d.dropna(subset=[y])
        if dd.Symbol.nunique() < 2: continue
        r = smf.ols(f"{y} ~ tr*post + trend + tr:trend", dd).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(dd.t)[0]})
        out[lab][y] = {"coef": float(r.params["tr:post"]), "se": float(r.bse["tr:post"]), "p": float(r.pvalues["tr:post"]), "n": int(r.nobs)}
        print(f"{lab:26s} {y:10s} {r.params['tr:post']:+.4f} (se {r.bse['tr:post']:.4f})")
syms = sorted(mq.Symbol.unique()); TR = ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "BANKEX"]
out["pooled_twfe"] = {}
for y in ["l_amihud", "cs_spread", "l_hl", "zero_days"]:
    d = mq.dropna(subset=[y])
    if d.Symbol.nunique() < 6: continue
    def tw(treated):
        x = d.copy(); x["D"] = (x.Symbol.isin(treated) & (x.post == 1)).astype(int)
        return smf.ols(f"{y} ~ D + C(Symbol) + C(t)", x).fit().params["D"]
    true = tw(TR); perm = [tw(list(c)) for c in itertools.combinations(sorted(d.Symbol.unique()), 4)]
    out["pooled_twfe"][y] = {"coef": float(true), "randomization_p": float(np.mean(np.abs(perm) >= abs(true) - 1e-12)), "n_assign": len(perm)}
    print("pooled", y, round(true, 4), "rand p", out["pooled_twfe"][y]["randomization_p"])
json.dump(out, open(config.RESULTS_DIR / "market_quality_did.json", "w"), indent=1)
