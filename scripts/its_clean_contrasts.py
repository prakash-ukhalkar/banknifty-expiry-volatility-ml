"""
Clean weekday-only contrasts for the settlement-weekday question. In the full-sample ITS the weekday and the
weekly-contract status change together after Nov 2024, so two within-structure contrasts are run:
  (A) weekly-contract era only (to 2024-11-13):   Thursday-weekly vs Wednesday-weekly
  (B) monthly-only era only (from 2024-11-14):    Monthly-Thursday vs Monthly-Tuesday
y ~ ExpiryWeek + NewRegime + ExpiryWeek:NewRegime + trend, Newey-West (5 lags).
"""
import json
import numpy as np, pandas as pd, statsmodels.api as sm
from src import config
from src.regime_calendar import tag_expiry_regime

df = pd.read_parquet(config.INTERIM_DATA_DIR / "banknifty_features_true.parquet")
df["Date"] = pd.to_datetime(df["Date"]); df["Regime"] = tag_expiry_regime(df["Date"])
df = df.dropna(subset=["Return", "Parkinson_Vol_1d", "Expiry_Week"]).reset_index(drop=True)
df["AbsReturn"] = df["Return"].abs()
out = {}
for lab, base, new in [("A_weekday_within_weekly_era", "Thursday-weekly", "Wednesday-weekly"),
                       ("B_weekday_within_monthly_only_era", "Monthly-only-Thursday", "Monthly-only-Tuesday")]:
    d = df[df.Regime.isin([base, new])].copy()
    d["New"] = (d.Regime == new).astype(float); d["EWxNew"] = d.Expiry_Week * d.New; d["Trend"] = np.arange(len(d))
    out[lab] = {"n": len(d)}
    for y in ["Return", "AbsReturn", "Parkinson_Vol_1d"]:
        r = sm.OLS(d[y], sm.add_constant(d[["Expiry_Week", "New", "EWxNew", "Trend"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        out[lab][y] = {"coef": float(r.params["EWxNew"]), "se": float(r.bse["EWxNew"]), "p": float(r.pvalues["EWxNew"])}
        print(f"{lab:36s} {y:18s} EWxNew={r.params['EWxNew']:+.5f} (se {r.bse['EWxNew']:.5f}) p={r.pvalues['EWxNew']:.3f} n={len(d)}")
json.dump(out, open(config.RESULTS_DIR / "its_clean_contrasts.json", "w"), indent=1)
