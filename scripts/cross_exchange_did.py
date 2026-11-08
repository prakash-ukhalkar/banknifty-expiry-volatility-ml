"""
Cross-exchange natural experiment on the true-expiry 6-index monthly panel (NSE: NIFTY control; BANKNIFTY, FINNIFTY,
MIDCPNIFTY treated.  BSE: SENSEX control; BANKEX treated).  Window 2023-06..2026-09, transition month 2024-11 dropped.
 A. within-exchange DiD (BN vs NIFTY; BANKEX vs SENSEX), outcomes: log total turnover, log expiry-day turnover, log expiry-day share
 B. pooled 6-index two-way-FE DiD (symbol FE + month FE) with exact randomization inference over the C(6,4)=15 treatment assignments
 C. substitution accounting with a pre-trend counterfactual for the two controls
 D. participant mix (NSE, market-wide index options): client / pro / FII shares pre vs post
Writes results/cross_exchange_did.json
"""
import itertools, json, glob
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from src import config

m = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet")
m["t"] = m.ym.dt.to_timestamp()
m = m[(m.t >= "2023-06-01") & (m.t < "2026-10-01") & (m.ym != pd.Period("2024-11")) & (m.tot > 0) & (m.exp_day > 0)].copy()
m["post"] = (m.t >= "2024-12-01").astype(int)
m["lt"], m["le"], m["ls"] = np.log(m.tot), np.log(m.exp_day), np.log(m.share)
m["trend"] = (m.t - pd.Timestamp("2023-06-01")).dt.days / 365.25
TREATED = ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "BANKEX"]
out = {}

# A ------------------------------------------------------------------------------------------------
for lab, (tr, ct) in {"NSE: BANKNIFTY vs NIFTY": ("BANKNIFTY", "NIFTY"), "BSE: BANKEX vs SENSEX": ("BANKEX", "SENSEX")}.items():
    d = m[m.Symbol.isin([tr, ct])].copy(); d["tr"] = (d.Symbol == tr).astype(int)
    out[lab] = {}
    for y in ["lt", "le", "ls"]:
        r = smf.ols(f"{y} ~ tr*post + trend + tr:trend", d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.t)[0]})
        out[lab][y] = {"coef": float(r.params["tr:post"]), "se": float(r.bse["tr:post"]), "p": float(r.pvalues["tr:post"]), "n": int(r.nobs)}
        print(f"A {lab:26s} {y}: {r.params['tr:post']:+.2f} (se {r.bse['tr:post']:.2f})")

# B ------------------------------------------------------------------------------------------------
syms = sorted(m.Symbol.unique()); print("symbols:", syms)
def twfe(d, treated, y):
    d = d.copy(); d["D"] = (d.Symbol.isin(treated) & (d.post == 1)).astype(int)
    return smf.ols(f"{y} ~ D + C(Symbol) + C(t)", d).fit().params["D"]
bal = m[m.Symbol.isin(syms)]
out["pooled_twfe"] = {}
for y in ["lt", "le", "ls"]:
    true = twfe(bal, TREATED, y)
    perm = [twfe(bal, list(c), y) for c in itertools.combinations(syms, len(TREATED))]
    p_two = float(np.mean(np.abs(perm) >= abs(true) - 1e-12))
    out["pooled_twfe"][y] = {"coef": float(true), "randomization_p_two_sided": p_two, "n_assignments": len(perm),
                             "rank_of_true_by_abs": int(sum(abs(np.array(perm)) > abs(true) + 1e-12) + 1)}
    print(f"B pooled TWFE {y}: {true:+.2f}, randomization p={p_two:.3f} over {len(perm)} assignments")

# C ------------------------------------------------------------------------------------------------
w = m.pivot(index="ym", columns="Symbol", values="tot")
pre = w.loc["2023-06":"2024-09"]; post = w.loc["2024-12":"2026-09"]
loss = float((pre[TREATED].sum(axis=1).mean() - post[TREATED].sum(axis=1).mean()))
gain_naive = float(sum(post[c].mean() - pre[c].mean() for c in ["NIFTY", "SENSEX"]))
yrs = float((post.index.to_timestamp().mean() - pre.index.to_timestamp().mean()).days / 365.25)
sens = {}
for g in [0.0, 0.25, 0.5, 1.0]:   # assumed organic annual growth of the two controls absent the reform
    cfl = sum(pre[c].mean() * (1 + g) ** yrs for c in ["NIFTY", "SENSEX"])
    sens[f"organic_growth_{int(g*100)}pct_per_year"] = float((sum(post[c].mean() for c in ["NIFTY", "SENSEX"]) - cfl) / loss)
out["substitution"] = {"treated_loss_per_month": loss, "controls_gain_naive": gain_naive, "years_between_period_midpoints": yrs,
                       "substitution_share_naive": gain_naive / loss, "substitution_share_by_assumed_organic_growth": sens,
                       "total_6index_change_pct_naive": float(post.sum(axis=1).mean() / pre.sum(axis=1).mean() - 1) * 100,
                       "sensex_gain_naive": float(post.SENSEX.mean() - pre.SENSEX.mean()), "nifty_gain_naive": float(post.NIFTY.mean() - pre.NIFTY.mean())}
print("C", json.dumps(out["substitution"], indent=0, default=float))

# D ------------------------------------------------------------------------------------------------
rows = []
for f in sorted(glob.glob(str(config.RAW_DATA_DIR / "nse_participant" / "vol_*.csv"))):
    try:
        x = pd.read_csv(f, skiprows=1); x.columns = [c.strip() for c in x.columns]; x["Client Type"] = x["Client Type"].str.strip()
        opt = lambda r: r["Option Index Call Long"] + r["Option Index Put Long"]
        tot = opt(x[x["Client Type"] == "TOTAL"].iloc[0])
        rec = {"Date": pd.to_datetime(f[-12:-4], format="%Y%m%d"), "opt_total_long": tot}
        for k in ["Client", "Pro", "FII", "DII"]: rec[k] = opt(x[x["Client Type"] == k].iloc[0]) / tot
        rows.append(rec)
    except Exception:
        pass
pt = pd.DataFrame(rows).set_index("Date").sort_index()
pt.to_parquet(config.INTERIM_DATA_DIR / "participant_index_options_share.parquet")
pm = pt.resample("QE").mean()
per = {"pre (2024-01..09)": pt.loc["2024-01":"2024-09"], "post (2025-01..2026-09)": pt.loc["2025-01":"2026-09"]}
out["participants"] = {k: {c: float(v[c].mean()) for c in ["Client", "Pro", "FII", "DII"]} | {"opt_total_long_mean": float(v.opt_total_long.mean())} for k, v in per.items()}
print("D", json.dumps(out["participants"], indent=0))
json.dump(out, open(config.RESULTS_DIR / "cross_exchange_did.json", "w"), indent=1)
