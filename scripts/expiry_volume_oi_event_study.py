"""
Replicates Vipul (2005)'s expiry-day abnormal volume/OI finding on Bank Nifty
derivatives, using NSE F&O Bhavcopy data (scripts/build_fo_volume_oi_dataset.py).
This is the paper's primary deliverable per the literature review: the one
consistently replicated effect across markets is abnormal volume/OI around
expiry, not next-day return direction (which scripts/walk_forward_backtest.py
and scripts/regime_shift_event_study.py both find null).

Two tests, matching Vipul's design:
1. Descriptive: is volume/OI on expiry day (and the day before/after) abnormally
   high relative to a same-weekday benchmark, within each settlement-day regime?
2. Regime-reform natural experiment: does the expiry-day volume/OI spike move to
   track whichever weekday the reform assigns (Thursday -> Wednesday -> Tuesday),
   i.e. is the spike mechanically tied to *being the expiry day* rather than to
   a specific calendar weekday?
"""
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import ttest_ind

from src import config
from src.regime_calendar import tag_expiry_regime, tag_liquidity_regime, WEEKLY_OPTIONS_CUTOVER


def load_data():
    fo = pd.read_parquet(config.INTERIM_DATA_DIR / "banknifty_fo_volume_oi.parquet")
    fo["Date"] = pd.to_datetime(fo["Date"])
    calendar = pd.read_csv(config.RAW_DATA_DIR / "nse_expiry_calendar.csv")
    expiry_dates = set(pd.to_datetime(calendar["ActualExpiry"]).dt.date)
    fo["Weekday"] = fo["Date"].dt.day_name()
    fo["IsExpiryDay"] = fo["Date"].dt.date.isin(expiry_dates)
    fo["Regime"] = tag_expiry_regime(fo["Date"])
    fo["LiquidityRegime"] = tag_liquidity_regime(fo["Date"])
    # Combined stratum: settlement-weekday regime x weekly-options-discontinuation
    # regime. Thursday-era and the pre-Nov-2024 part of Wednesday-era both had
    # BANKNIFTY weekly options; the post-Nov-2024 part of Wednesday-era and all
    # of Tuesday-era are monthly-only. This lets the Wednesday-era internal split
    # (same settlement weekday, different liquidity regime) isolate the weekly-
    # options effect cleanly from the settlement-weekday effect.
    fo["Stratum"] = fo["Regime"] + " / " + fo["LiquidityRegime"]
    fo["DayBeforeExpiry"] = fo["IsExpiryDay"].shift(-1).fillna(False)
    fo["DayAfterExpiry"] = fo["IsExpiryDay"].shift(1).fillna(False)
    return fo


def expiry_vs_nonexpiry_same_weekday(df, value_col, group_col, weekday_by_group):
    """
    Benchmark: within each group (settlement-regime x liquidity-regime stratum),
    compare expiry days to NON-expiry days that fall on the SAME weekday as that
    group's expiry day. This controls for generic weekday seasonality (Vipul's
    benchmark logic) AND, when group_col='Stratum', for the weekly-options-
    discontinuation liquidity shift that's a separate confound from settlement
    weekday.
    """
    rows = []
    for group, weekday in weekday_by_group.items():
        sub = df[(df[group_col] == group) & (df["Weekday"] == weekday)]
        if len(sub) == 0:
            continue
        expiry = sub[sub["IsExpiryDay"]][value_col]
        non_expiry = sub[~sub["IsExpiryDay"]][value_col]
        if len(expiry) < 2 or len(non_expiry) < 2:
            continue
        tstat, pval = ttest_ind(expiry, non_expiry, equal_var=False)
        pct_increase = (expiry.mean() / non_expiry.mean() - 1) * 100 if non_expiry.mean() != 0 else np.nan
        rows.append({
            group_col: group,
            "Benchmark_Weekday": weekday,
            "N_Expiry": len(expiry),
            "N_NonExpiry_SameWeekday": len(non_expiry),
            f"Mean_{value_col}_Expiry": float(expiry.mean()),
            f"Mean_{value_col}_NonExpiry_SameWeekday": float(non_expiry.mean()),
            "Pct_Increase": float(pct_increase),
            "Welch_t_stat": float(tstat),
            "Welch_p_value": float(pval),
        })
    return rows


def event_window_profile(df, value_col, window=3):
    """Average value_col on expiry day and +/- `window` trading days around it, by regime."""
    df = df.sort_values("Date").reset_index(drop=True)
    expiry_idx = df.index[df["IsExpiryDay"]].tolist()
    profile = {offset: [] for offset in range(-window, window + 1)}
    regime_for_offset = {offset: [] for offset in range(-window, window + 1)}
    for idx in expiry_idx:
        for offset in range(-window, window + 1):
            j = idx + offset
            if 0 <= j < len(df):
                profile[offset].append(df.loc[j, value_col])
                regime_for_offset[offset].append(df.loc[idx, "Regime"])
    return {
        str(offset): {"mean": float(np.mean(vals)), "n": len(vals)}
        for offset, vals in profile.items() if vals
    }


def pooled_interaction_regression(df, value_col):
    """
    log(value) ~ IsExpiryDay * LiquidityRegime + weekday FE + trend, HAC SEs.
    Pools all strata (much more power than the small-N stratum t-tests) while
    still isolating the liquidity-regime effect via the interaction term and
    controlling for generic weekday seasonality via weekday fixed effects.
    Settlement-weekday regime is NOT included as a separate control because it's
    almost perfectly collinear with weekday-of-week itself (each settlement
    regime trades/expires on a specific weekday) -- the weekday FE already
    absorbs that.
    """
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
    print(f"Loaded {len(df)} F&O volume/OI rows, {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(df.groupby("Stratum")["Date"].agg(["min", "max", "count"]))

    # Which weekday is "expiry day" in each stratum (settlement-regime x liquidity-regime).
    expiry_weekday_by_stratum = (
        df[df["IsExpiryDay"]].groupby("Stratum")["Weekday"].agg(lambda s: s.mode()[0]).to_dict()
    )
    print(f"\nExpiry weekday by stratum: {expiry_weekday_by_stratum}")

    results = {}
    for value_col in ["Total_Volume", "Total_OpenInterest"]:
        print(f"\n=== Expiry day vs. same-weekday non-expiry benchmark, by Stratum (settlement x liquidity regime): {value_col} ===")
        rows = expiry_vs_nonexpiry_same_weekday(df, value_col, "Stratum", expiry_weekday_by_stratum)
        for row in rows:
            print(row)
        results[f"expiry_vs_nonexpiry_by_stratum_{value_col}"] = rows

        print(f"\n=== Event window profile (expiry day +/- 3 trading days): {value_col} ===")
        profile = event_window_profile(df, value_col)
        print(profile)
        results[f"event_window_{value_col}"] = profile

    # Clean, well-identified test: WITHIN Wednesday-era only (settlement weekday
    # held constant), does expiry-day volume/OI concentration change when weekly
    # options are discontinued? This isolates the liquidity-regime effect from
    # the settlement-weekday effect.
    print("\n=== Weekly-options discontinuation effect, holding settlement weekday constant (Wednesday-era only) ===")
    wed = df[df["Regime"] == "Wednesday-era"]
    wed_liq_results = {}
    for value_col in ["Total_Volume", "Total_OpenInterest"]:
        rows = expiry_vs_nonexpiry_same_weekday(
            wed, value_col, "LiquidityRegime",
            {"Weekly-Options": "Wednesday", "Monthly-Only": "Wednesday"},
        )
        for row in rows:
            print(value_col, row)
        wed_liq_results[value_col] = rows
    results["weekly_options_discontinuation_within_wednesday_era"] = wed_liq_results

    # Pooled interaction regression -- the primary, best-powered test.
    print("\n=== Pooled regression: log(Volume) ~ IsExpiry * MonthlyOnly + weekday FE + trend (HAC) ===")
    vol_model = pooled_interaction_regression(df, "Total_Volume")
    print(vol_model.summary())
    results["pooled_regression_log_volume"] = {
        "params": {k: float(v) for k, v in vol_model.params.items()},
        "p_values": {k: float(v) for k, v in vol_model.pvalues.items()},
        "n_obs": int(vol_model.nobs),
        "r_squared": float(vol_model.rsquared),
    }

    print("\n=== Pooled regression: log(OpenInterest) ~ IsExpiry * MonthlyOnly + weekday FE + trend (HAC) ===")
    oi_model = pooled_interaction_regression(df, "Total_OpenInterest")
    print(oi_model.summary())
    results["pooled_regression_log_oi"] = {
        "params": {k: float(v) for k, v in oi_model.params.items()},
        "p_values": {k: float(v) for k, v in oi_model.pvalues.items()},
        "n_obs": int(oi_model.nobs),
        "r_squared": float(oi_model.rsquared),
    }

    out_path = config.RESULTS_DIR / "expiry_volume_oi_event_study.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    run()
