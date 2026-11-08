"""How much does the choice of expiry calendar matter?  Same monthly Bank Nifty-vs-Nifty DiD (window 2023-06..2026-09, Nov-2024 dropped) with expiry days defined
 (a) from the exchange files (true), (b) from the rule-based calendar (data/raw/nse_expiry_calendar.csv) applied to both indices.
Also reports the original daily ratio-of-ratios triple interaction (old specification, rule-based calendar) for reference.  Writes results/calendar_sensitivity.json"""
import json
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from src import config

p = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet"); p = p[p.Symbol.isin(["BANKNIFTY", "NIFTY"])].copy()
ex = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_dates.parquet")
old = set(pd.to_datetime(pd.read_csv(config.RAW_DATA_DIR / "nse_expiry_calendar.csv").ActualExpiry))
p["ym"] = p.Date.dt.to_period("M")
true_m = ex[ex.IsMonthly].rename(columns={"ExpiryDate": "Date"})[["Symbol", "Date"]].assign(T=True)
p = p.merge(true_m, how="left", on=["Symbol", "Date"]); p["T"] = p["T"].fillna(False).astype(bool); p["O"] = p.Date.isin(old)


def monthly(flag):
    g = p.groupby(["Symbol", "ym"])
    m = pd.DataFrame({"tot": g.Value_Total.sum(), "e": p[p[flag]].groupby(["Symbol", "ym"]).Value_Total.sum()}).reset_index()
    m = m[(m.e > 0) & (m.tot > 0)]; m["t"] = m.ym.dt.to_timestamp()
    m = m[(m.t >= "2023-06-01") & (m.t < "2026-10-01") & (m.ym != pd.Period("2024-11"))].copy()
    m["post"] = (m.t >= "2024-12-01").astype(int); m["tr"] = (m.Symbol == "BANKNIFTY").astype(int)
    m["trend"] = (m.t - pd.Timestamp("2023-06-01")).dt.days / 365.25
    m["le"], m["ls"] = np.log(m.e), np.log(m.e / m.tot)
    return m


out = {}
for lab, flag in [("true_expiry_dates", "T"), ("rule_based_calendar", "O")]:
    m = monthly(flag); out[lab] = {}
    for y in ["le", "ls"]:
        r = smf.ols(f"{y} ~ tr*post + trend + tr:trend", m).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(m.t)[0]})
        out[lab][y] = {"coef": float(r.params["tr:post"]), "se": float(r.bse["tr:post"]), "p": float(r.pvalues["tr:post"]), "n": int(r.nobs)}
        print(lab, y, round(r.params["tr:post"], 3), round(r.bse["tr:post"], 3))
# original daily ratio-of-ratios (expiry-day vs other-day), rule-based calendar, same window
d = p[(p.Date >= "2023-06-01") & (p.Date < "2026-10-01") & (p.ym != pd.Period("2024-11"))].copy()
for lab, flag in [("true_expiry_dates", "T"), ("rule_based_calendar", "O")]:
    x = d.copy(); x["ex"] = x[flag].astype(int); x["post"] = (x.Date >= "2024-12-01").astype(int); x["tr"] = (x.Symbol == "BANKNIFTY").astype(int)
    x["lv"] = np.log1p(x.Value_Total); x["trend"] = (x.Date - x.Date.min()).dt.days / 365.25; x["wd"] = x.Date.dt.day_name()
    r = smf.ols("lv ~ ex*post*tr + trend + trend:tr + C(wd)", x).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    out.setdefault("daily_ratio_of_ratios", {})[lab] = {"coef": float(r.params["ex:post:tr"]), "se": float(r.bse["ex:post:tr"])}
    print("daily triple interaction", lab, round(r.params["ex:post:tr"], 3))
json.dump(out, open(config.RESULTS_DIR / "calendar_sensitivity.json", "w"), indent=1)
