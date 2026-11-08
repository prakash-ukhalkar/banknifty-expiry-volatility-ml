"""
Bank Nifty settlement regimes (TRUE, from the Bhavcopy expiry field): Thursday-weekly -> Wednesday-weekly
(2023-09-06) -> Monthly-only-Thursday (2024-11-14, weekly contract retired) -> Monthly-only-Tuesday (2025-09-01).
Shared by the walk-forward evaluation and the regime-shift ITS. The old rule-based calendar is kept as LEGACY.
"""
import pandas as pd

LEGACY_REGIME_BOUNDARIES = [  # WRONG: from the rule-based calendar; kept only for comparison
    (pd.Timestamp("1900-01-01"), pd.Timestamp("2024-02-29"), "Thursday-era"),
    (pd.Timestamp("2024-03-01"), pd.Timestamp("2025-08-31"), "Wednesday-era"),
    (pd.Timestamp("2025-09-01"), pd.Timestamp("2100-01-01"), "Tuesday-era"),
]

# TRUE Bank Nifty settlement regimes, from the Bhavcopy expiry field (scripts/build_index_expiry_panel.py):
#  - weekly options expired Thursday until 2023-09-05; Wednesday from 2023-09-06 (last weekly 2024-11-13)
#  - after the weekly contract was retired the monthly expiry was the last Thursday (Jan-Aug 2025)
#  - from Sep 2025 the monthly expiry is the last Tuesday
# NOTE: weekday and weekly-contract status change together, so regimes are NOT separable
# from the weekly-contract removal; the Monthly-only regimes carry both changes.
REGIME_BOUNDARIES = [
    (pd.Timestamp("1900-01-01"), pd.Timestamp("2023-09-05"), "Thursday-weekly"),
    (pd.Timestamp("2023-09-06"), pd.Timestamp("2024-11-13"), "Wednesday-weekly"),
    (pd.Timestamp("2024-11-14"), pd.Timestamp("2025-08-31"), "Monthly-only-Thursday"),
    (pd.Timestamp("2025-09-01"), pd.Timestamp("2100-01-01"), "Monthly-only-Tuesday"),
]
REGIME_NAMES = [r[2] for r in REGIME_BOUNDARIES]

TRANSITION_DATES = {
    "Thursday_to_Wednesday_weekly": pd.Timestamp("2023-09-06"),
    "Weekly_removal_to_Monthly_Thursday": pd.Timestamp("2024-11-14"),
    "Monthly_Thursday_to_Tuesday": pd.Timestamp("2025-09-01"),
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
