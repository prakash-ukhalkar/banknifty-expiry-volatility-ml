"""
Parse BSE derivatives market-summary files (data/raw/bse_fo/MS_*.csv) into the same (Symbol, Date) schema as the
NSE panel, plus true expiry dates, then write the combined 6-index monthly panel used by the cross-exchange DiD.
BSE value column is "in thousands" (verified: qty x avg price ~ value x 1000) -> multiplied by 1000.
Symbols: SENSEX (asset BSX), BANKEX (BKX). SX50 / BIT ignored. Lot size is not in this format, so notional OI is not built for BSE.
Outputs: data/interim/bse_expiry_panel.parquet, bse_expiry_dates.parquet, monthly_expiry_panel_all.parquet
"""
import numpy as np, pandas as pd
from src import config

ASSET = {"BSX": "SENSEX", "BKX": "BANKEX"}
COLS = list(pd.read_csv(next((config.RAW_DATA_DIR / "bse_fo").glob("MS_20250115.csv")), nrows=0).columns)
files = sorted((config.RAW_DATA_DIR / "bse_fo").glob("MS_*.csv"))
rows = []
for f in files:
    try:
        x = pd.read_csv(f)
        if "Product Type" not in x.columns:  # header-less one-row files
            x = pd.read_csv(f, header=None, names=COLS)
    except Exception:
        continue
    x = x[x["Product Type"].isin(["IO", "IF"]) & x["Asset Code"].isin(ASSET)].copy()
    if x.empty:
        continue
    x["Symbol"] = x["Asset Code"].map(ASSET)
    x["Date"] = pd.to_datetime(x["Market Summary Date"], format="%d %b %Y", errors="coerce")
    x["Expiry"] = pd.to_datetime(x["Expiry Date"], format="%d %b %Y", errors="coerce")
    x["IsOption"] = x["Product Type"] == "IO"
    x["Value"] = x["Total Traded Value (in Thousands)(absolute)"].astype(float) * 1000.0
    x["Volume"] = x["Total Traded Quantity"].astype(float); x["OI"] = x["Open Interest"].astype(float)
    opt = x[x.IsOption]; g = ["Symbol", "Date"]
    today = opt[opt.Expiry == opt.Date]
    s = pd.DataFrame({"Value_Total": x.groupby(g).Value.sum(), "Value_Options": opt.groupby(g).Value.sum(),
                      "Volume_Options": opt.groupby(g).Volume.sum(), "OI_Options": opt.groupby(g).OI.sum(),
                      "OI_Futures": x[~x.IsOption].groupby(g).OI.sum(),
                      "Value_ExpiringToday": today.groupby(g).Value.sum(), "Volume_ExpiringToday": today.groupby(g).Volume.sum(),
                      "NExpiriesListed": opt[opt.OI > 0].groupby(g).Expiry.nunique()})
    rows.append(s.fillna({"Value_ExpiringToday": 0.0, "Volume_ExpiringToday": 0.0}).reset_index())
bse = pd.concat(rows, ignore_index=True).sort_values(["Symbol", "Date"]).reset_index(drop=True)
bse["LotSize"] = np.nan
bse.to_parquet(config.INTERIM_DATA_DIR / "bse_expiry_panel.parquet", index=False)
ex = bse[bse.Value_ExpiringToday > 0][["Symbol", "Date"]].rename(columns={"Date": "ExpiryDate"})
ex["YM"] = ex.ExpiryDate.dt.to_period("M")
ex["IsMonthly"] = ex.groupby(["Symbol", "YM"]).ExpiryDate.transform("max") == ex.ExpiryDate
ex.drop(columns="YM").to_parquet(config.INTERIM_DATA_DIR / "bse_expiry_dates.parquet", index=False)

# combined monthly panel (NSE 4 + BSE 2)
p = pd.concat([pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet"), bse], ignore_index=True)
e = pd.concat([pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_dates.parquet"),
               pd.read_parquet(config.INTERIM_DATA_DIR / "bse_expiry_dates.parquet")], ignore_index=True)
p["ym"] = p.Date.dt.to_period("M")
mon = e[e.IsMonthly].rename(columns={"ExpiryDate": "Date"})[["Symbol", "Date"]].assign(M=True)
anyx = e.rename(columns={"ExpiryDate": "Date"})[["Symbol", "Date"]].assign(A=True)
p = p.merge(mon, how="left", on=["Symbol", "Date"]).merge(anyx, how="left", on=["Symbol", "Date"])
p["M"] = p.M.fillna(False).astype(bool); p["A"] = p.A.fillna(False).astype(bool)
g = p.groupby(["Symbol", "ym"])
m = pd.DataFrame({"tot": g.Value_Total.sum(), "opt": g.Value_Options.sum(),
                  "exp_day": p[p.M].groupby(["Symbol", "ym"]).Value_Total.sum(),
                  "exp_contracts": p[p.M].groupby(["Symbol", "ym"]).Value_ExpiringToday.sum(),
                  "nexp": g.A.sum(), "ndays": g.Date.count()}).reset_index()
m["share"] = m.exp_day / m.tot
m.to_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet", index=False)
print(bse.groupby("Symbol").Date.agg(["min", "max", "count"]))
for s_ in ["SENSEX", "BANKEX", "NIFTY"]:
    x = m[m.Symbol == s_].set_index("ym")
    for a, b in [("2024-01", "2024-09"), ("2025-01", "2025-08"), ("2025-10", "2026-09")]:
        y = x.loc[a:b]; print(s_, a, "tot %.2e exp_day %.2e share %.3f nexp %.1f" % (y.tot.mean(), y.exp_day.mean(), y.share.mean(), y.nexp.mean()))
