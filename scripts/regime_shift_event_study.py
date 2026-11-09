"""
Regime-shift natural experiment: does the expiry-week return/volatility effect change
across the SEBI-mandated settlement-day reforms (Thursday -> Wednesday -> Tuesday)?

This replaces next-day-return *prediction* (which scripts/walk_forward_backtest.py shows
does not survive honest out-of-fold evaluation) as the study's primary empirical claim.
The settlement-day changes are a genuine natural experiment: they were imposed by the
regulator on a fixed calendar, independent of market conditions, so comparing expiry-week
behavior before and after each change is a cleaner identification strategy than treating
the calendar as just another ML feature.

Two complementary tests:
1. Descriptive: mean/std of daily log return and realized volatility in expiry week vs.
   non-expiry week, within each regime, with Welch t-tests.
2. Formal interrupted-time-series (diff-in-diff style) OLS:
     y_t = a + b1*ExpiryWeek_t + b2*Wednesday_t + b3*Tuesday_t
           + b4*(ExpiryWeek_t * Wednesday_t) + b5*(ExpiryWeek_t * Tuesday_t)
           + b6*trend_t + e_t
   with HAC (Newey-West) standard errors for serial correlation. b4/b5 test whether the
   expiry-week effect size shifted after each reform (Thursday-era is the omitted baseline).
   y is Return for the return-effect test and realized volatility (Rolling_Vol) for the
   volatility-effect test.
"""
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import ttest_ind

from src import config
from src.regime_calendar import tag_expiry_regime, TRANSITION_DATES, REGIME_NAMES


def load_data():
    df = pd.read_parquet(config.INTERIM_DATA_DIR / "banknifty_features_true.parquet")
    df["Date"] = pd.to_datetime(df["Date"])
    df["Regime"] = tag_expiry_regime(df["Date"])
    df = df.dropna(subset=["Return", "Rolling_Vol", "Parkinson_Vol_1d", "GarmanKlass_Vol_1d", "Expiry_Week"]).reset_index(drop=True)
    df["Trend"] = np.arange(len(df))
    df["AbsReturn"] = df["Return"].abs()
    return df


def descriptive_by_regime(df, value_col):
    rows = []
    for regime in REGIME_NAMES:
        sub = df[df["Regime"] == regime]
        if len(sub) == 0:
            continue
        ew = sub[sub["Expiry_Week"] == 1][value_col]
        non_ew = sub[sub["Expiry_Week"] == 0][value_col]
        if len(ew) < 2 or len(non_ew) < 2:
            continue
        tstat, pval = ttest_ind(ew, non_ew, equal_var=False)
        rows.append({
            "Regime": regime,
            "N_ExpiryWeek": len(ew),
            "N_NonExpiryWeek": len(non_ew),
            f"Mean_{value_col}_ExpiryWeek": float(ew.mean()),
            f"Mean_{value_col}_NonExpiryWeek": float(non_ew.mean()),
            f"Std_{value_col}_ExpiryWeek": float(ew.std()),
            f"Std_{value_col}_NonExpiryWeek": float(non_ew.std()),
            "Welch_t_stat": float(tstat),
            "Welch_p_value": float(pval),
        })
    return rows


def interrupted_time_series(df, value_col):
    """Diff-in-diff style OLS with HAC (Newey-West) SEs, Thursday-era as baseline."""
    d = df.copy()
    others = REGIME_NAMES[1:]  # Thursday-weekly is the omitted baseline
    cols = ["Expiry_Week"]
    for r in others:
        d[r] = (d["Regime"] == r).astype(float)
        d["EW_x_" + r] = d["Expiry_Week"] * d[r]
    cols += others + ["EW_x_" + r for r in others] + ["Trend"]
    X = sm.add_constant(d[cols])
    y = d[value_col]

    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return model


def model_to_dict(model, label):
    return {
        "label": label,
        "params": {k: float(v) for k, v in model.params.items()},
        "p_values": {k: float(v) for k, v in model.pvalues.items()},
        "conf_int_lower": {k: float(v) for k, v in model.conf_int()[0].items()},
        "conf_int_upper": {k: float(v) for k, v in model.conf_int()[1].items()},
        "n_obs": int(model.nobs),
        "r_squared": float(model.rsquared),
    }


def run():
    df = load_data()
    print(f"Loaded {len(df)} rows, {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(df.groupby("Regime")["Date"].agg(["min", "max", "count"]))

    print("\n=== Descriptive: Return, expiry week vs. non-expiry week, by regime ===")
    return_desc = descriptive_by_regime(df, "Return")
    for row in return_desc:
        print(row)

    print("\n=== Descriptive: Realized volatility (Rolling_Vol), expiry week vs. non-expiry week, by regime ===")
    vol_desc = descriptive_by_regime(df, "Rolling_Vol")
    for row in vol_desc:
        print(row)

    print("\n=== Descriptive: Parkinson range-based volatility, expiry week vs. non-expiry week, by regime ===")
    parkinson_desc = descriptive_by_regime(df, "Parkinson_Vol_1d")
    for row in parkinson_desc:
        print(row)

    print("\n=== Descriptive: Garman-Klass range-based volatility, expiry week vs. non-expiry week, by regime ===")
    gk_desc = descriptive_by_regime(df, "GarmanKlass_Vol_1d")
    for row in gk_desc:
        print(row)

    print("\n=== Interrupted time series: Return ~ ExpiryWeek * Regime + trend (HAC SEs) ===")
    return_model = interrupted_time_series(df, "Return")
    print(return_model.summary())

    print("\n=== Interrupted time series: |Return| (volatility proxy) ~ ExpiryWeek * Regime + trend (HAC SEs) ===")
    absret_model = interrupted_time_series(df, "AbsReturn")
    print(absret_model.summary())

    print("\n=== Interrupted time series: Rolling_Vol ~ ExpiryWeek * Regime + trend (HAC SEs) ===")
    vol_model = interrupted_time_series(df, "Rolling_Vol")
    print(vol_model.summary())

    print("\n=== Interrupted time series: Parkinson range vol ~ ExpiryWeek * Regime + trend (HAC SEs) ===")
    parkinson_model = interrupted_time_series(df, "Parkinson_Vol_1d")
    print(parkinson_model.summary())

    print("\n=== Interrupted time series: Garman-Klass range vol ~ ExpiryWeek * Regime + trend (HAC SEs) ===")
    gk_model = interrupted_time_series(df, "GarmanKlass_Vol_1d")
    print(gk_model.summary())

    out = {
        "n_obs": len(df),
        "regime_date_ranges": {
            regime: {
                "start": str(sub["Date"].min().date()),
                "end": str(sub["Date"].max().date()),
                "n": int(len(sub)),
            }
            for regime, sub in df.groupby("Regime")
        },
        "transition_dates": {k: str(v.date()) for k, v in TRANSITION_DATES.items()},
        "descriptive_return_by_regime": return_desc,
        "descriptive_volatility_by_regime": vol_desc,
        "descriptive_parkinson_vol_by_regime": parkinson_desc,
        "descriptive_garman_klass_vol_by_regime": gk_desc,
        "its_return_model": model_to_dict(return_model, "Return ~ ExpiryWeek*Regime + trend"),
        "its_absreturn_model": model_to_dict(absret_model, "|Return| ~ ExpiryWeek*Regime + trend"),
        "its_rolling_vol_model": model_to_dict(vol_model, "Rolling_Vol ~ ExpiryWeek*Regime + trend"),
        "its_parkinson_vol_model": model_to_dict(parkinson_model, "Parkinson_Vol_1d ~ ExpiryWeek*Regime + trend"),
        "its_garman_klass_vol_model": model_to_dict(gk_model, "GarmanKlass_Vol_1d ~ ExpiryWeek*Regime + trend"),
    }
    out_path = config.RESULTS_DIR / "regime_shift_event_study_true_calendar.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    run()
