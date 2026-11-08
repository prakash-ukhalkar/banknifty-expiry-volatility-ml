# Legacy result files (do not cite)
`metrics_summary.json`, `ols_vs_xgb_comparison.json` and `models/` belong to the retired next-day return
prediction paper (Sharpe ~2.1 on a 147-day test). The walk-forward evidence supersedes them (no predictability).
`diff_in_diff_banknifty_vs_nifty.json`, `event_study_leads_lags.json`, `nifty_control_event_study.json` and
`expiry_volume_oi_event_study.json` were built on `data/raw/nse_expiry_calendar.csv`, which is WRONG for 8 of 23
post-reform Bank Nifty expiries and 10 of 23 Nifty expiries (see `corrected_robustness.json`, `calendar_audit`).
Corrected results: `did_monthly_true_expiry.json`, `corrected_robustness.json`, `figures/fig1_*`, `fig2_*`.
