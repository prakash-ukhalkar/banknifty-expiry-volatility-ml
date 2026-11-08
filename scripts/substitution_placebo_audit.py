"""
Corrected-design analyses on the true-expiry panel:
 1. calendar audit: old rule-based calendar vs true expiries (how many flags were wrong)
 2. substitution: do losses on delisted-weekly indices line up with gains on NIFTY?
 3. in-time placebo (randomization) inference for the BN-vs-NIFTY DiD using PRE-period data only
 4. BN-only before/after (no control) and window-sensitivity of the DiD
Outputs results/corrected_*.json
"""
import json
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from src import config

R = config.RESULTS_DIR
m = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel.parquet")
m["t"] = m["ym"].dt.to_timestamp()
p = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet")
ex = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_dates.parquet")
out = {}

# 1. calendar audit -----------------------------------------------------------
cal = pd.read_csv(config.RAW_DATA_DIR / "nse_expiry_calendar.csv")
old = set(pd.to_datetime(cal["ActualExpiry"]))
aud = {}
for s in ["BANKNIFTY", "NIFTY"]:
    true_m = set(ex[(ex.Symbol == s) & ex.IsMonthly].ExpiryDate)
    rng = [d for d in true_m if d >= pd.Timestamp("2020-01-01")]
    ok = [d for d in rng if d in old]
    wrong_post = [d for d in rng if d not in old and d >= pd.Timestamp("2024-11-14")]
    aud[s] = {"true_monthly_expiries": len(rng), "matched_by_old_calendar": len(ok),
              "mismatched": len(rng) - len(ok), "mismatched_since_2024-11-14": len(wrong_post)}
out["calendar_audit"] = aud
print("calendar audit", aud)

# 2. substitution -------------------------------------------------------------
w = m.pivot(index="ym", columns="Symbol", values="tot")
pre, post = w.loc["2024-01":"2024-09"], w.loc["2025-01":"2025-08"].combine_first(w.loc["2025-10":"2026-09"])
post = pd.concat([w.loc["2025-01":"2025-08"], w.loc["2025-10":"2026-09"]])
d_del = (post[["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]].sum(axis=1).mean() - pre[["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]].sum(axis=1).mean())
d_nf = post["NIFTY"].mean() - pre["NIFTY"].mean()
sub = {"delisted_change_INR_per_month": d_del, "nifty_change_INR_per_month": d_nf,
       "nifty_gain_as_share_of_delisted_loss": -d_nf / d_del,
       "nifty_share_of_4index_turnover_pre": float(pre["NIFTY"].sum() / pre.sum().sum()),
       "nifty_share_of_4index_turnover_post": float(post["NIFTY"].sum() / post.sum().sum()),
       "four_index_total_change_pct": float(post.sum(axis=1).mean() / pre.sum(axis=1).mean() - 1) * 100}
out["substitution"] = sub
print("substitution", {k: round(v, 3) if abs(v) < 1e6 else f"{v:.3e}" for k, v in sub.items()})
# market-wide trend caveat: NIFTY growth in 2022-2023 as benchmark
g = w.loc["2023-01":"2023-09", "NIFTY"].mean() / w.loc["2022-01":"2022-09", "NIFTY"].mean() - 1
out["nifty_yoy_growth_2023_vs_2022_pct"] = float(g) * 100
print("NIFTY organic yoy growth 2023 vs 2022: %.0f%%" % (g * 100))

# 3. in-time placebo ----------------------------------------------------------
def did_coef(df, y, cut):
    df = df.copy()
    df["post"] = (df.t >= cut).astype(int)
    df["tr"] = (df.Symbol == "BANKNIFTY").astype(int)
    df["trend"] = (df.t - df.t.min()).dt.days / 365.25
    r = smf.ols(f"{y} ~ tr*post + trend + tr:trend", df).fit()
    return r.params["tr:post"]

base = m[m.Symbol.isin(["BANKNIFTY", "NIFTY"]) & (m.exp_day > 0)].copy()
base["lt"], base["le"], base["ls"] = np.log(base.tot), np.log(base.exp_day), np.log(base.share)
prem = base[base.t < "2024-10-01"]
true_df = base[base.ym != pd.Period("2024-11")]
pl = {}
for y in ["lt", "le", "ls"]:
    t_true = did_coef(true_df, y, pd.Timestamp("2024-12-01"))
    fakes = [did_coef(prem, y, c) for c in pd.date_range("2021-07-01", "2024-01-01", freq="MS")]
    fakes = np.array(fakes)
    pl[y] = {"true": float(t_true), "placebo_mean": float(fakes.mean()), "placebo_min": float(fakes.min()),
             "placebo_max": float(fakes.max()), "n_placebos": len(fakes),
             "rand_p_two_sided": float((np.abs(fakes) >= abs(t_true)).mean())}
    print("placebo", y, {k: round(v, 3) for k, v in pl[y].items()})
out["in_time_placebo"] = pl

# 4. BN-only and window sensitivity -------------------------------------------
bn = base[(base.Symbol == "BANKNIFTY") & (base.ym != pd.Period("2024-11"))].copy()
bn["post"] = (bn.t >= "2024-12-01").astype(int); bn["trend"] = (bn.t - bn.t.min()).dt.days / 365.25
bno = {}
for y in ["lt", "le", "ls"]:
    r = smf.ols(f"{y} ~ post + trend", bn).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    bno[y] = {"coef": float(r.params["post"]), "se": float(r.bse["post"])}
out["bn_only_before_after"] = bno
print("BN only", bno)
win = {}
for lab, a, b in [("2023-01..2026-10", "2023-01", "2026-12"), ("2024-01..2026-10", "2024-01", "2026-12"),
                  ("2024-01..2025-08", "2024-01", "2025-08"), ("2022-01..2026-10", "2022-01", "2026-12")]:
    d = true_df[(true_df.ym >= pd.Period(a)) & (true_df.ym <= pd.Period(b))]
    win[lab] = {y: float(did_coef(d, y, pd.Timestamp("2024-12-01"))) for y in ["lt", "le", "ls"]}
out["window_sensitivity"] = win
print("windows", win)
json.dump(out, open(R / "corrected_robustness.json", "w"), indent=1, default=float)
