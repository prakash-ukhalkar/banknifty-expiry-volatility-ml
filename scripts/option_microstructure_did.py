"""
Option-level microstructure outcomes (contract panel) + placebo + dose-response, then the same within-exchange DiDs and pooled
two-way-FE with exact randomization inference as scripts/cross_exchange_did.py.
Monthly outcomes per index (traded index-option contracts only):
  dte01_share   share of turnover in contracts with 0-1 days to expiry
  dte07_share   share of turnover in contracts with 0-7 days to expiry
  otm5_share    share of turnover in options with |K/S - 1| > 5%   (far-OTM / lottery-like)
  atm_cs        value-weighted Corwin-Schultz high-low spread of ATM (|K/S-1|<2%) options with 2-30 days to expiry
  atm_hl        value-weighted log(High/Low) range of the same options
Placebo: stock-F&O aggregate turnover (never had weeklies).  Dose-response: daily BN-vs-NIFTY log turnover gap on the number of
Bank Nifty option expiries listed, Oct-Dec 2024.
Writes results/option_microstructure_did.json and data/interim/option_micro_monthly.parquet
"""
import itertools, json
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from src import config

o = pd.read_parquet(config.INTERIM_DATA_DIR / "options_contracts.parquet")
o = o[(o.Date >= "2023-01-01") & (o.Value > 0) & o.Und.notna() & (o.Und > 0)].copy()
o["dte"] = (o.Expiry - o.Date).dt.days
o["mny"] = (o.Strike / o.Und - 1).abs()
o["ym"] = o.Date.dt.to_period("M")
g = ["Symbol", "ym"]
tot = o.groupby(g).Value.sum()
sh = lambda mask: (o[mask].groupby(g).Value.sum() / tot).reindex(tot.index).fillna(0)
mm = pd.DataFrame({"tot_opt": tot, "dte01_share": sh(o.dte <= 1), "dte07_share": sh(o.dte <= 7), "otm5_share": sh(o.mny > 0.05)})

# ATM option high-low spread (Corwin-Schultz) on consecutive trading days of the same contract
a = o[(o.mny < 0.02) & (o.dte >= 2) & (o.dte <= 30) & (o.H > 0) & (o.L > 0)].sort_values(["Symbol", "Expiry", "Strike", "Type", "Date"]).copy()
days = {s: {d: i for i, d in enumerate(sorted(o[o.Symbol == s].Date.unique()))} for s in o.Symbol.unique()}
a["di"] = [days[s][d] for s, d in zip(a.Symbol, a.Date)]
k = ["Symbol", "Expiry", "Strike", "Type"]
a["H1"], a["L1"], a["di1"] = a.groupby(k).H.shift(1), a.groupby(k).L.shift(1), a.groupby(k).di.shift(1)
a = a[(a.di - a.di1 == 1)].copy()
beta = np.log(a.H / a.L) ** 2 + np.log(a.H1 / a.L1) ** 2
gam = np.log(np.maximum(a.H, a.H1) / np.minimum(a.L, a.L1)) ** 2
kk = 3 - 2 * np.sqrt(2)
al = (np.sqrt(2 * beta) - np.sqrt(beta)) / kk - np.sqrt(gam / kk)
a["cs"] = (2 * (np.exp(al) - 1) / (1 + np.exp(al))).clip(lower=0)
a["hl"] = np.log(a.H / a.L)
a = a.replace([np.inf, -np.inf], np.nan).dropna(subset=["cs", "hl"])
w = a.assign(cw=a.cs * a.Value, hw=a.hl * a.Value).groupby(g)[["cw", "hw", "Value"]].sum()
mm["atm_cs"] = w.cw / w.Value; mm["atm_hl"] = w.hw / w.Value
mm = mm.reset_index(); mm["t"] = mm.ym.dt.to_timestamp()
mm.to_parquet(config.INTERIM_DATA_DIR / "option_micro_monthly.parquet", index=False)

mm = mm[(mm.t >= "2023-06-01") & (mm.t < "2026-10-01") & (mm.ym != pd.Period("2024-11")) & (mm.tot_opt > 0)].copy()
mm["post"] = (mm.t >= "2024-12-01").astype(int); mm["trend"] = (mm.t - pd.Timestamp("2023-06-01")).dt.days / 365.25
OUT = ["dte01_share", "dte07_share", "otm5_share", "atm_cs", "atm_hl"]
out = {"descriptives": {s: {p: {y: float(mm[(mm.Symbol == s) & (mm.post == pv)][y].mean()) for y in OUT} for p, pv in [("pre", 0), ("post", 1)]}
                        for s in sorted(mm.Symbol.unique())}}
for lab, (tr, ct) in {"NSE: BANKNIFTY vs NIFTY": ("BANKNIFTY", "NIFTY"), "BSE: BANKEX vs SENSEX": ("BANKEX", "SENSEX")}.items():
    d = mm[mm.Symbol.isin([tr, ct])].copy(); d["tr"] = (d.Symbol == tr).astype(int); out[lab] = {}
    for y in OUT:
        dd = d.dropna(subset=[y])
        if dd.Symbol.nunique() < 2 or len(dd) < 20: continue
        r = smf.ols(f"{y} ~ tr*post + trend + tr:trend", dd).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(dd.t)[0]})
        out[lab][y] = {"coef": float(r.params["tr:post"]), "se": float(r.bse["tr:post"]), "p": float(r.pvalues["tr:post"]), "n": int(r.nobs)}
        print(f"{lab:26s} {y:12s} {r.params['tr:post']:+.4f} (se {r.bse['tr:post']:.4f}) p={r.pvalues['tr:post']:.3f}")
TR = ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "BANKEX"]; out["pooled_twfe"] = {}
for y in OUT:
    d = mm.dropna(subset=[y]); syms = sorted(d.Symbol.unique())
    if len(syms) < 6: continue
    def tw(treated):
        x = d.copy(); x["D"] = (x.Symbol.isin(treated) & (x.post == 1)).astype(int)
        return smf.ols(f"{y} ~ D + C(Symbol) + C(t)", x).fit().params["D"]
    true = tw(TR); perm = [tw(list(c)) for c in itertools.combinations(syms, 4)]
    out["pooled_twfe"][y] = {"coef": float(true), "randomization_p": float(np.mean(np.abs(perm) >= abs(true) - 1e-12))}
    print("pooled", y, round(true, 4), "rand p", out["pooled_twfe"][y]["randomization_p"])

# placebo: stock F&O (never had weeklies) vs the index panel -----------------------------------------------------
st = pd.read_parquet(config.INTERIM_DATA_DIR / "stock_fo_daily.parquet"); st["ym"] = st.Date.dt.to_period("M")
sm_ = st.groupby("ym")[["Value_StockOpt", "Value_StockFut"]].sum(); sm_["tot"] = sm_.sum(axis=1)
pm = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet").pivot(index="ym", columns="Symbol", values="tot")
pre_ = slice("2024-01", "2024-09"); post_ = slice("2025-01", "2026-09")
out["stock_placebo"] = {"stock_fo_post_over_pre": float(sm_.loc[post_, "tot"].mean() / sm_.loc[pre_, "tot"].mean()),
                        **{f"{s}_post_over_pre": float(pm.loc[post_, s].mean() / pm.loc[pre_, s].mean()) for s in pm.columns}}
print("stock placebo", {k: round(v, 3) for k, v in out["stock_placebo"].items()})

# dose-response ---------------------------------------------------------------------------------------------------
p = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet")
d = p[(p.Date >= "2024-09-01") & (p.Date <= "2024-12-31") & p.Symbol.isin(["BANKNIFTY", "NIFTY"])].pivot(index="Date", columns="Symbol", values=["Value_Total", "NExpiriesListed"])
dd = pd.DataFrame({"gap": np.log(d[("Value_Total", "BANKNIFTY")]) - np.log(d[("Value_Total", "NIFTY")]), "nexp": d[("NExpiriesListed", "BANKNIFTY")]}).dropna()
dd["wd"] = dd.index.day_name()
r = smf.ols("gap ~ nexp + C(wd)", dd).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
out["dose_response"] = {"coef_per_listed_expiry": float(r.params["nexp"]), "se": float(r.bse["nexp"]), "p": float(r.pvalues["nexp"]), "n": int(r.nobs)}
print("dose-response", out["dose_response"])
json.dump(out, open(config.RESULTS_DIR / "option_microstructure_did.json", "w"), indent=1, default=float)
