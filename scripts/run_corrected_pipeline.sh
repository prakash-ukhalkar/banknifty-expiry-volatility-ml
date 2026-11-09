#!/usr/bin/env bash
# Corrected pipeline (run from repo root). Step 1 takes ~15 min (parses ~1,700 Bhavcopy zips).
python -m scripts.build_index_expiry_panel
python - <<'PY'
# monthly panel used by steps 2-4
import pandas as pd
from src import config
p=pd.read_parquet(config.INTERIM_DATA_DIR/"index_expiry_panel.parquet"); ex=pd.read_parquet(config.INTERIM_DATA_DIR/"index_expiry_dates.parquet")
p["ym"]=p.Date.dt.to_period("M")
mon=ex[ex.IsMonthly].rename(columns={"ExpiryDate":"Date"})[["Symbol","Date"]].assign(M=True)
anyx=ex.rename(columns={"ExpiryDate":"Date"})[["Symbol","Date"]].assign(A=True)
p=p.merge(mon,how="left",on=["Symbol","Date"]).merge(anyx,how="left",on=["Symbol","Date"]); p["M"]=p.M.fillna(False); p["A"]=p.A.fillna(False)
g=p.groupby(["Symbol","ym"])
m=pd.DataFrame({"tot":g.Value_Total.sum(),"opt":g.Value_Options.sum(),"exp_day":p[p.M].groupby(["Symbol","ym"]).Value_Total.sum(),
 "exp_contracts":p[p.M].groupby(["Symbol","ym"]).Value_ExpiringToday.sum(),"nexp":g.A.sum()}).reset_index()
m["share"]=m.exp_day/m.tot; m.to_parquet(config.INTERIM_DATA_DIR/"monthly_expiry_panel.parquet")
PY
python -m scripts.did_monthly_true_expiry
python -m scripts.substitution_placebo_audit
python -m scripts.make_corrected_figures
# --- extension: BSE control, participant mix, market quality ---
python -m scripts.download_bse_and_participant_data
python -m scripts.build_bse_expiry_panel
python -m scripts.cross_exchange_did
python -m scripts.build_futures_liquidity_panel   # ~15 min
python -m scripts.market_quality_did
# --- secondary analyses on the true calendar ---
python -m scripts.build_features_true_calendar
python -m scripts.regime_shift_event_study
python -m scripts.its_clean_contrasts
python -m scripts.walk_forward_backtest
python -m scripts.make_corrected_figures
# --- option-level panel, placebo, dose-response ---
python -m scripts.build_option_contract_panel     # ~5 min
python -m scripts.option_microstructure_did
python -m scripts.make_corrected_figures
python -m scripts.build_notebooks
python -m pytest tests -q
# --- additional robustness analyses ---
python -m scripts.calendar_sensitivity
python -m scripts.pretrend_sensitivity
python -m scripts.pretrend_robust_ci          # ~10 min
python -m scripts.migration_stock_benchmark

