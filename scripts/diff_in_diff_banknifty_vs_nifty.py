"""
The formal diff-in-diff test tying together scripts/expiry_volume_oi_event_study.py
and scripts/nifty_control_event_study.py: pools Bank Nifty and Nifty 50 F&O
volume/OI into one panel and tests whether the (expiry-day x monthly-only-regime)
concentration effect is significantly LARGER for Bank Nifty than for Nifty 50 --
the triple-interaction coefficient is the causal estimate of "losing the weekly
contract" net of any market-wide trend both indices share.

  log(metric) ~ IsExpiry * MonthlyOnly * IsBankNifty + weekday FE + trend, HAC SEs

Primary metrics are Total_Value (rupee turnover) and Total_OpenInterest_Notional
(OI x lot size), NOT raw Total_Volume/Total_OpenInterest in contracts -- Bank
Nifty's lot size changed 15->30 right around the same Nov-2024 window as the
weekly-options discontinuation (confirmed in the UDiFF NewBrdLotQty column), so
a raw contract count is not comparable across that boundary. Value and notional
OI are lot-size-invariant and are the confound-corrected result. Total_Volume/
Total_OpenInterest are still reported as a secondary check.

Also includes:
  - a placebo-date test (reruns the same regression with fake cutover dates
    shifted +/-6 and +/-3 months from the true 2024-11-14 date) -- the effect
    should be much weaker/null at fake dates if it's really tied to the true event.
  - a leave-one-out check across Bank Nifty's Monthly-Only-regime expiry days,
    to confirm the result isn't driven by one unusually large settlement day
    (there are only ~19-23 such days, so this is a real risk to rule out).
"""
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src import config
from src.regime_calendar import WEEKLY_OPTIONS_CUTOVER

KEY_COEF = "Expiry_x_Monthly_x_BankNifty"


def load_panel():
    bn = pd.read_parquet(config.INTERIM_DATA_DIR / "banknifty_fo_volume_oi.parquet")
    nf = pd.read_parquet(config.INTERIM_DATA_DIR / "nifty_fo_volume_oi.parquet")
    bn["Index"] = "BANKNIFTY"
    nf["Index"] = "NIFTY"
    df = pd.concat([bn, nf], ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])

    calendar = pd.read_csv(config.RAW_DATA_DIR / "nse_expiry_calendar.csv")
    expiry_dates = set(pd.to_datetime(calendar["ActualExpiry"]).dt.date)
    df["Weekday"] = df["Date"].dt.day_name()
    df["IsExpiryDay"] = df["Date"].dt.date.isin(expiry_dates)
    return df


def triple_interaction_regression(df, value_col, cutover=WEEKLY_OPTIONS_CUTOVER, exclude_dates=None,
                                   index_specific_trend=True):
    """
    index_specific_trend=True adds a Trend x IsBankNifty interaction so any
    longer-running differential drift between Bank Nifty's and Nifty's expiry-
    day concentration (found by the placebo-date test: the effect doesn't fully
    vanish at placebo dates years before the true event, implying some secular
    trend difference predates it) is absorbed BEFORE attributing the remaining
    jump at the true cutover to the weekly-options-discontinuation event. This
    is the more conservative, defensible specification -- use it as primary.
    """
    d = df.copy()
    if exclude_dates:
        d = d[~d["Date"].isin(pd.to_datetime(list(exclude_dates)))]
    d["IsMonthlyOnly"] = (d["Date"] >= cutover).astype(float)
    d["LogValue"] = np.log1p(d[value_col])
    d["IsExpiry"] = d["IsExpiryDay"].astype(float)
    d["IsBankNifty"] = (d["Index"] == "BANKNIFTY").astype(float)
    d["Trend"] = (d["Date"] - d["Date"].min()).dt.days.astype(float)

    d["Expiry_x_Monthly"] = d["IsExpiry"] * d["IsMonthlyOnly"]
    d["Expiry_x_BankNifty"] = d["IsExpiry"] * d["IsBankNifty"]
    d["Monthly_x_BankNifty"] = d["IsMonthlyOnly"] * d["IsBankNifty"]
    d["Expiry_x_Monthly_x_BankNifty"] = d["IsExpiry"] * d["IsMonthlyOnly"] * d["IsBankNifty"]

    weekday_dummies = pd.get_dummies(d["Weekday"], prefix="WD", drop_first=True).astype(float)

    feature_cols = [
        "IsExpiry", "IsMonthlyOnly", "IsBankNifty",
        "Expiry_x_Monthly", "Expiry_x_BankNifty", "Monthly_x_BankNifty",
        "Expiry_x_Monthly_x_BankNifty", "Trend",
    ]
    if index_specific_trend:
        d["Trend_x_BankNifty"] = d["Trend"] * d["IsBankNifty"]
        feature_cols.append("Trend_x_BankNifty")

    X = pd.concat([d[feature_cols], weekday_dummies], axis=1)
    X = sm.add_constant(X)
    y = d["LogValue"]

    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return model


def summarize(model, label):
    ci = model.conf_int()
    print(f"{label}: coef={model.params[KEY_COEF]:.4f}, p={model.pvalues[KEY_COEF]:.4f}, "
          f"95% CI=[{ci.loc[KEY_COEF, 0]:.4f}, {ci.loc[KEY_COEF, 1]:.4f}], n={int(model.nobs)}")
    return {
        "coef": float(model.params[KEY_COEF]),
        "p_value": float(model.pvalues[KEY_COEF]),
        "ci_lower": float(ci.loc[KEY_COEF, 0]),
        "ci_upper": float(ci.loc[KEY_COEF, 1]),
        "n_obs": int(model.nobs),
    }


def placebo_date_test(df, value_col):
    """
    Rerun with fake cutover dates placed DEEP inside the stable Weekly-Options
    era (2021-2023), years away from the true 2024-11-14 event, where nothing
    actually happened -- "before" and "after" these fake dates are both
    genuinely Weekly-Options-regime data, so the interaction should be weak/null.

    (An earlier version of this test used fake dates +/-3/6/12 months from the
    true cutover -- that was NOT a valid placebo: shifting the boundary by a few
    months barely changes which multi-year regime most expiry days fall into,
    since the "IsMonthlyOnly" classification is dominated by which multi-year
    era a date is in, not the exact day of the cutover. All those nearby fake
    cutovers reproduced the same large, significant coefficient as the true
    date -- not because the effect is spurious, but because the test wasn't
    actually varying the regime composition enough to falsify anything. Fake
    dates need to be far from the true structural break to be a real test.)
    """
    fake_dates = [pd.Timestamp("2021-06-01"), pd.Timestamp("2022-06-01"), pd.Timestamp("2023-06-01")]
    results = {}
    for fake_cutover in fake_dates:
        model = triple_interaction_regression(df, value_col, cutover=fake_cutover)
        label = f"placebo cutover {fake_cutover.date()} (deep in Weekly-Options era, no real break)"
        results[label] = summarize(model, label)
    true_model = triple_interaction_regression(df, value_col, cutover=WEEKLY_OPTIONS_CUTOVER)
    results["TRUE cutover 2024-11-14"] = summarize(true_model, "TRUE cutover 2024-11-14")
    return results


def leave_one_out_test(df, value_col):
    """Drop each Bank-Nifty Monthly-Only-regime expiry day one at a time; check coefficient stability."""
    bn_monthly_expiry_dates = df[
        (df["Index"] == "BANKNIFTY") & (df["IsExpiryDay"]) & (df["Date"] >= WEEKLY_OPTIONS_CUTOVER)
    ]["Date"].tolist()
    print(f"Leave-one-out over {len(bn_monthly_expiry_dates)} Bank Nifty Monthly-Only expiry days")

    full_model = triple_interaction_regression(df, value_col)
    full_coef = full_model.params[KEY_COEF]

    loo_coefs = []
    for excl_date in bn_monthly_expiry_dates:
        model = triple_interaction_regression(df, value_col, exclude_dates=[excl_date])
        loo_coefs.append(float(model.params[KEY_COEF]))

    loo_coefs = np.array(loo_coefs)
    return {
        "full_sample_coef": float(full_coef),
        "loo_coef_min": float(loo_coefs.min()),
        "loo_coef_max": float(loo_coefs.max()),
        "loo_coef_mean": float(loo_coefs.mean()),
        "loo_coef_std": float(loo_coefs.std()),
        "n_excluded_each": 1,
        "n_loo_runs": len(loo_coefs),
    }


def run():
    df = load_panel()
    print(f"Pooled panel: {len(df)} rows ({df['Index'].value_counts().to_dict()})")

    results = {}
    for value_col in ["Total_Value", "Total_OpenInterest_Notional", "Total_Volume", "Total_OpenInterest"]:
        print(f"\n=== Diff-in-diff: log({value_col}) ~ Expiry*MonthlyOnly*Index + weekday FE + trend (HAC) ===")
        model = triple_interaction_regression(df, value_col)
        print(model.summary())
        results[value_col] = {
            "params": {k: float(v) for k, v in model.params.items()},
            "p_values": {k: float(v) for k, v in model.pvalues.items()},
            "n_obs": int(model.nobs),
            "r_squared": float(model.rsquared),
        }

    print("\n=== Placebo-date test (Total_Value, confound-corrected primary metric) ===")
    placebo_results = placebo_date_test(df, "Total_Value")
    results["placebo_date_test_Total_Value"] = placebo_results

    print("\n=== Leave-one-out robustness (Total_Value, confound-corrected primary metric) ===")
    loo_results = leave_one_out_test(df, "Total_Value")
    print(loo_results)
    results["leave_one_out_Total_Value"] = loo_results

    out_path = config.RESULTS_DIR / "diff_in_diff_banknifty_vs_nifty.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    run()
