"""
Data-based benchmark for the migration share. The two retained indices (Nifty 50, Sensex) would have grown even without the rule, so the raw
share of lost turnover that 'moved' to them overstates migration. Aggregate stock futures and options never had weekly contracts and were
not touched by the rule; their growth between the same windows is used as an observed proxy for organic derivatives-market growth.
Windows match scripts/cross_exchange_did.py (pre = 2023-06..2024-09, post = 2024-12..2026-09). Writes results/migration_stock_benchmark.json.
Stock-derivative turnover is scaled by a multiplier m in {1, 1.25, 1.5, 2} to allow the retained index contracts to have grown faster than stocks.
"""
import json
import numpy as np, pandas as pd
from src import config

TREATED = ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "BANKEX"]; RETAINED = ["NIFTY", "SENSEX"]
ma = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet")
w = ma.pivot(index="ym", columns="Symbol", values="tot")
st = pd.read_parquet(config.INTERIM_DATA_DIR / "stock_fo_daily.parquet"); st["ym"] = st.Date.dt.to_period("M")
stm = st.groupby("ym")[["Value_StockOpt", "Value_StockFut"]].sum().sum(axis=1)
pre_i, post_i = slice("2023-06", "2024-09"), slice("2024-12", "2026-09")
pre, post = w.loc[pre_i], w.loc[post_i]
loss = float(pre[TREATED].sum(axis=1).mean() - post[TREATED].sum(axis=1).mean())
g = float(stm.loc[post_i].mean() / stm.loc[pre_i].mean())
act = float(sum(post[c].mean() for c in RETAINED)); base = float(sum(pre[c].mean() for c in RETAINED))
out = {"stock_fo_growth_factor": g, "lost_turnover_per_month": loss, "retained_pre": base, "retained_post": act,
       "retained_growth_factor": act / base, "migrated_share_by_multiplier": {}}
for mult in [1.0, 1.25, 1.5, 2.0]:
    cf = base * g * mult
    out["migrated_share_by_multiplier"][f"x{mult}"] = {"counterfactual_retained": cf, "migrated_share": float((act - cf) / loss)}
    print(f"multiplier {mult}: migrated share = {(act - cf) / loss:.2f}")
print("stock growth factor", round(g, 3), "retained growth factor", round(act / base, 3))
json.dump(out, open(config.RESULTS_DIR / "migration_stock_benchmark.json", "w"), indent=1)
