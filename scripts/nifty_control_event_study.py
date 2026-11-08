"""
Placebo/control test for the Bank Nifty weekly-options-discontinuation finding
(scripts/expiry_volume_oi_event_study.py): Nifty 50 KEPT its weekly options
contract through the same Nov 2024 SEBI rule change (NSE chose to retain NIFTY
weekly, not BANKNIFTY), so if the Bank Nifty volume-concentration effect is
really caused by losing the weekly contract, Nifty 50 should show no analogous
shift in its expiry-day-vs-normal-day volume/OI ratio around the same date.

Reuses nse_expiry_calendar.csv for expiry *dates* (same monthly settlement-day
regimes historically applied NSE-wide before the Tuesday/Wednesday reforms
diverged by product) -- see caveat printed below re: Nifty 50's own expiry-day
weekday history, which should be checked against this calendar's assumptions.
"""
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src import config
from src.regime_calendar import tag_expiry_regime, tag_liquidity_regime


def load_data():
    fo = pd.read_parquet(config.INTERIM_DATA_DIR / "nifty_fo_volume_oi.parquet")
    fo["Date"] = pd.to_datetime(fo["Date"])
    calendar = pd.read_csv(config.RAW_DATA_DIR / "nse_expiry_calendar.csv")
    expiry_dates = set(pd.to_datetime(calendar["ActualExpiry"]).dt.date)
    fo["Weekday"] = fo["Date"].dt.day_name()
    fo["IsExpiryDay"] = fo["Date"].dt.date.isin(expiry_dates)
    fo["Regime"] = tag_expiry_regime(fo["Date"])
    fo["LiquidityRegime"] = tag_liquidity_regime(fo["Date"])
    return fo


def pooled_interaction_regression(df, value_col):
    d = df.copy()
    d["LogValue"] = np.log1p(d[value_col])
    d["IsExpiry"] = d["IsExpiryDay"].astype(float)
    d["IsMonthlyOnly"] = (d["LiquidityRegime"] == "Monthly-Only").astype(float)
    d["Expiry_x_MonthlyOnly"] = d["IsExpiry"] * d["IsMonthlyOnly"]
    d["Trend"] = np.arange(len(d))

    weekday_dummies = pd.get_dummies(d["Weekday"], prefix="WD", drop_first=True).astype(float)
    X = pd.concat([d[["IsExpiry", "IsMonthlyOnly", "Expiry_x_MonthlyOnly", "Trend"]], weekday_dummies], axis=1)
    X = sm.add_constant(X)
    y = d["LogValue"]

    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return model


def run():
    df = load_data()
    print(f"Loaded {len(df)} NIFTY F&O volume/OI rows, {df['Date'].min().date()} to {df['Date'].max().date()}")
    print("NOTE: NIFTY kept its own weekly options throughout -- this uses the same")
    print("nse_expiry_calendar.csv MONTHLY expiry dates as the Bank Nifty study, as a")
    print("like-for-like comparison of the monthly-settlement day specifically.\n")

    results = {}
    for value_col in ["Total_Volume", "Total_OpenInterest"]:
        print(f"=== NIFTY placebo regression: log({value_col}) ~ IsExpiry * MonthlyOnly + weekday FE + trend (HAC) ===")
        model = pooled_interaction_regression(df, value_col)
        print(model.summary())
        results[f"pooled_regression_log_{value_col}"] = {
            "params": {k: float(v) for k, v in model.params.items()},
            "p_values": {k: float(v) for k, v in model.pvalues.items()},
            "n_obs": int(model.nobs),
            "r_squared": float(model.rsquared),
        }
        print()

    out_path = config.RESULTS_DIR / "nifty_control_event_study.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    run()
