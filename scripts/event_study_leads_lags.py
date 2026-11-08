"""
Event-study (leads/lags) version of the Bank-Nifty-vs-Nifty-50 diff-in-diff, to
distinguish a genuine discontinuous jump at the true Nov-2024 weekly-options
cutover from a smooth pre-existing trend (the simple before/after diff-in-diff
in scripts/diff_in_diff_banknifty_vs_nifty.py cannot tell these apart: its
placebo-date test showed the "effect" growing smoothly as the fake cutover
approached the true date, even after adding an index-specific linear trend
control, which only rules out a LINEAR differential drift).

Design: bin trading days into half-year periods relative to the true event
(period 0 = the half-year containing 2024-11-14), estimate a separate
Expiry x BankNifty coefficient for every period, with the period immediately
before the event (period -1) as the omitted reference. If the effect is a real
discontinuity, periods well before the event should show small/flat
coefficients close to 0, with a clear jump starting at period 0 or shortly
after. If it's a smooth secular trend, the coefficients should climb steadily
across ALL periods with no distinguishable jump right at the event.
"""
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src import config
from src.regime_calendar import WEEKLY_OPTIONS_CUTOVER


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


def assign_half_year_period(dates, event_date=WEEKLY_OPTIONS_CUTOVER):
    """Integer half-year index relative to the event: 0 = half-year containing event."""
    months_from_event = (dates.dt.year - event_date.year) * 12 + (dates.dt.month - event_date.month)
    return (months_from_event // 6).astype(int)


def event_study_regression(df, value_col, reference_period=-1):
    d = df.copy()
    d["LogValue"] = np.log1p(d[value_col])
    d["IsExpiry"] = d["IsExpiryDay"].astype(float)
    d["IsBankNifty"] = (d["Index"] == "BANKNIFTY").astype(float)
    d["Period"] = assign_half_year_period(d["Date"])
    d["Trend"] = (d["Date"] - d["Date"].min()).dt.days.astype(float)

    periods = sorted(d["Period"].unique())
    periods = [p for p in periods if p != reference_period]

    # Period main effects, Period x BankNifty, Period x Expiry, and the key
    # Period x Expiry x BankNifty leads/lags (reference period omitted).
    period_dummies = pd.get_dummies(d["Period"], prefix="P", drop_first=False).astype(float)
    period_dummies = period_dummies.drop(columns=[f"P_{reference_period}"])

    for p in periods:
        d[f"PxBN_{p}"] = (d["Period"] == p).astype(float) * d["IsBankNifty"]
        d[f"PxEW_{p}"] = (d["Period"] == p).astype(float) * d["IsExpiry"]
        d[f"EventCoef_{p}"] = (d["Period"] == p).astype(float) * d["IsExpiry"] * d["IsBankNifty"]

    weekday_dummies = pd.get_dummies(d["Weekday"], prefix="WD", drop_first=True).astype(float)

    base_cols = ["IsExpiry", "IsBankNifty", "Trend"]
    pxbn_cols = [f"PxBN_{p}" for p in periods]
    pxew_cols = [f"PxEW_{p}" for p in periods]
    event_cols = [f"EventCoef_{p}" for p in periods]

    X = pd.concat(
        [d[base_cols], period_dummies, d[pxbn_cols], d[pxew_cols], d[event_cols], weekday_dummies],
        axis=1,
    )
    X = sm.add_constant(X)
    y = d["LogValue"]

    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return model, periods


def run():
    df = load_panel()
    print(f"Pooled panel: {len(df)} rows")

    results = {}
    for value_col in ["Total_Value", "Total_OpenInterest_Notional"]:
        print(f"\n=== Event-study leads/lags: log({value_col}), Expiry x BankNifty x Period (ref=-1, HAC) ===")
        model, periods = event_study_regression(df, value_col)

        rows = []
        for p in periods:
            coef_name = f"EventCoef_{p}"
            ci = model.conf_int()
            rows.append({
                "period_half_years_from_event": p,
                "coef": float(model.params[coef_name]),
                "p_value": float(model.pvalues[coef_name]),
                "ci_lower": float(ci.loc[coef_name, 0]),
                "ci_upper": float(ci.loc[coef_name, 1]),
            })
        rows.sort(key=lambda r: r["period_half_years_from_event"])
        for r in rows:
            sig = "*" if r["p_value"] < 0.05 else " "
            print(f"  period {r['period_half_years_from_event']:+3d}: coef={r['coef']:+.4f} "
                  f"(p={r['p_value']:.4f}){sig}  CI=[{r['ci_lower']:.3f},{r['ci_upper']:.3f}]")
        results[value_col] = rows

    out_path = config.RESULTS_DIR / "event_study_leads_lags.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    run()
