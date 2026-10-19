"""
SEBI-mandated weekly-expiry settlement-day calendar: Thursday -> Wednesday (Mar 2024)
-> Tuesday (Sep 2025), per data/raw/nse_expiry_calendar.csv. Shared by the walk-forward
ML evaluation and the regime-shift event study so both use the same regime boundaries.
"""
import pandas as pd

REGIME_BOUNDARIES = [
    (pd.Timestamp("1900-01-01"), pd.Timestamp("2024-02-29"), "Thursday-era"),
    (pd.Timestamp("2024-03-01"), pd.Timestamp("2025-08-31"), "Wednesday-era"),
    (pd.Timestamp("2025-09-01"), pd.Timestamp("2100-01-01"), "Tuesday-era"),
]

TRANSITION_DATES = {
    "Thursday_to_Wednesday": pd.Timestamp("2024-03-01"),
    "Wednesday_to_Tuesday": pd.Timestamp("2025-09-01"),
}

# SEBI's "one weekly index-derivatives contract per exchange" rule (effective
# Nov 2024) forced NSE to retire Bank Nifty WEEKLY options -- verified directly
# in the F&O Bhavcopy data: distinct BANKNIFTY option expiries listed on any
# given day dropped from 10 (several weeklies + monthly far-dates) to 6 (monthly
# only) between 2024-10-17 and 2024-11-14; the last BANKNIFTY weekly expiry
# traded 2024-11-13, and 2024-11-27 is the first monthly-only expiry going
# forward. This is a SEPARATE event from the Thursday->Wednesday->Tuesday
# settlement-day reform above (it falls in the middle of the Wednesday-era
# window) and is the dominant driver of the later volume/OI level shift --
# any volume/OI comparison must condition on this, not just on settlement weekday.
WEEKLY_OPTIONS_CUTOVER = pd.Timestamp("2024-11-14")


def tag_expiry_regime(dates):
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    labels = pd.Series("Unknown", index=dates.index)
    for start, end, name in REGIME_BOUNDARIES:
        labels[(dates >= start) & (dates <= end)] = name
    return labels


def tag_liquidity_regime(dates):
    """'Weekly-Options' (BANKNIFTY had its own weekly expiries) vs 'Monthly-Only'
    (post SEBI single-weekly-contract rule, from 2024-11-14)."""
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    return pd.Series(
        ["Monthly-Only" if d >= WEEKLY_OPTIONS_CUTOVER else "Weekly-Options" for d in dates],
        index=dates.index,
    )
