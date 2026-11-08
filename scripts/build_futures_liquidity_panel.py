"""
Near-month index-FUTURES daily series (OHLC, settle, value, OI) for NSE (Bhavcopy, both formats) and BSE (market summary),
used for market-quality proxies (Amihud illiquidity, Corwin-Schultz high-low spread, zero-trade days) in
scripts/market_quality_did.py.  Output: data/interim/futures_daily.parquet  (Symbol, Date, O,H,L,C,Settle,Value,Volume,OI,Expiry)
"""
import zipfile
import numpy as np, pandas as pd
from src import config

NSE = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
LEG = config.RAW_DATA_DIR / "fo_bhavcopy" / "legacy"; UDI = config.RAW_DATA_DIR / "fo_bhavcopy" / "udiff"


def rd(path, cols):
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as f:
        return pd.read_csv(f, usecols=lambda c: c in cols)


def legacy(p):
    d = rd(p, {"INSTRUMENT", "SYMBOL", "EXPIRY_DT", "OPEN", "HIGH", "LOW", "CLOSE", "SETTLE_PR", "CONTRACTS", "VAL_INLAKH", "OPEN_INT", "TIMESTAMP"})
    d = d[(d.INSTRUMENT == "FUTIDX") & d.SYMBOL.isin(NSE)]
    return pd.DataFrame({"Symbol": d.SYMBOL, "Date": pd.to_datetime(d.TIMESTAMP, format="%d-%b-%Y", errors="coerce"),
                         "Expiry": pd.to_datetime(d.EXPIRY_DT, format="%d-%b-%Y", errors="coerce"), "O": d.OPEN, "H": d.HIGH, "L": d.LOW,
                         "C": d.CLOSE, "Settle": d.SETTLE_PR, "Value": d.VAL_INLAKH * 1e5, "Volume": d.CONTRACTS, "OI": d.OPEN_INT})


def udiff(p):
    d = rd(p, {"TradDt", "FinInstrmTp", "TckrSymb", "XpryDt", "OpnPric", "HghPric", "LwPric", "ClsPric", "SttlmPric", "TtlTrfVal", "TtlTradgVol", "OpnIntrst"})
    d = d[(d.FinInstrmTp == "IDF") & d.TckrSymb.isin(NSE)]
    return pd.DataFrame({"Symbol": d.TckrSymb, "Date": pd.to_datetime(d.TradDt), "Expiry": pd.to_datetime(d.XpryDt), "O": d.OpnPric, "H": d.HghPric,
                         "L": d.LwPric, "C": d.ClsPric, "Settle": d.SttlmPric, "Value": d.TtlTrfVal, "Volume": d.TtlTradgVol, "OI": d.OpnIntrst})


parts = []
for p in sorted(LEG.glob("*.zip")):
    try: parts.append(legacy(p))
    except Exception as e: print("fail", p.name, e)
for p in sorted(UDI.glob("*.zip")):
    try: parts.append(udiff(p))
    except Exception as e: print("fail", p.name, e)
# BSE
COLS = list(pd.read_csv(config.RAW_DATA_DIR / "bse_fo" / "MS_20250115.csv", nrows=0).columns)
for f in sorted((config.RAW_DATA_DIR / "bse_fo").glob("MS_*.csv")):
    x = pd.read_csv(f)
    if "Product Type" not in x.columns: x = pd.read_csv(f, header=None, names=COLS)
    x = x[(x["Product Type"] == "IF") & x["Asset Code"].isin(["BSX", "BKX"])]
    if x.empty: continue
    parts.append(pd.DataFrame({"Symbol": x["Asset Code"].map({"BSX": "SENSEX", "BKX": "BANKEX"}),
                               "Date": pd.to_datetime(x["Market Summary Date"], format="%d %b %Y", errors="coerce"),
                               "Expiry": pd.to_datetime(x["Expiry Date"], format="%d %b %Y", errors="coerce"),
                               "O": x["Open Price"], "H": x["High Price"], "L": x["Low Price"], "C": x["Close Price"], "Settle": x["Close Price"],
                               "Value": x["Total Traded Value (in Thousands)(absolute)"] * 1000.0, "Volume": x["Total Traded Quantity"], "OI": x["Open Interest"]}))
f = pd.concat(parts, ignore_index=True).dropna(subset=["Date", "Expiry"])
f = f[f.Expiry >= f.Date].sort_values(["Symbol", "Date", "Expiry"])
near = f.groupby(["Symbol", "Date"]).head(1).reset_index(drop=True)   # nearest-expiry contract
near.to_parquet(config.INTERIM_DATA_DIR / "futures_daily.parquet", index=False)
print(near.groupby("Symbol").Date.agg(["min", "max", "count"]))
