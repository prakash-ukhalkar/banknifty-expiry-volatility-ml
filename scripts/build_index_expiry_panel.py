"""
Rebuild the daily index-derivatives panel with TRUE per-index expiry information
taken from the Bhavcopy expiry field (EXPIRY_DT / XpryDt), instead of the single
rule-based calendar in data/raw/nse_expiry_calendar.csv (which was found to flag
the wrong day for several months and was applied to both indices).

Output (data/interim/index_expiry_panel.parquet), one row per (Symbol, Date):
  Value_Total        futures + options traded value (INR)
  Value_Options      options traded value (INR)
  Value_ExpiringToday  options value in contracts whose expiry == Date
  Volume_Options, OI_Options, OI_Futures, LotSize
  NExpiriesListed    number of distinct option expiries with open interest
And data/interim/index_expiry_dates.parquet: (Symbol, ExpiryDate, IsMonthly)
where an expiry date is "true" if option contracts with that expiry traded on
that very date, and IsMonthly marks the last such expiry in each calendar month.
"""
import zipfile
import numpy as np
import pandas as pd

from src import config

LEGACY_DIR = config.RAW_DATA_DIR / "fo_bhavcopy" / "legacy"
UDIFF_DIR = config.RAW_DATA_DIR / "fo_bhavcopy" / "udiff"
SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]


def _read(path, usecols):
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as f:
            return pd.read_csv(f, usecols=lambda c: c in usecols)


def parse_legacy(path):
    cols = {"INSTRUMENT", "SYMBOL", "EXPIRY_DT", "CONTRACTS", "VAL_INLAKH", "OPEN_INT", "TIMESTAMP", "SETTLE_PR"}
    df = _read(path, cols)
    df = df[df["SYMBOL"].isin(SYMBOLS) & df["INSTRUMENT"].isin(["FUTIDX", "OPTIDX"])].copy()
    if df.empty:
        return None
    return pd.DataFrame({
        "Symbol": df["SYMBOL"],
        "Date": pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y", errors="coerce"),
        "Expiry": pd.to_datetime(df["EXPIRY_DT"], format="%d-%b-%Y", errors="coerce"),
        "IsOption": df["INSTRUMENT"] == "OPTIDX",
        "Volume": df["CONTRACTS"].astype(float),
        "Value": df["VAL_INLAKH"].astype(float) * 1e5,
        "OI": df["OPEN_INT"].astype(float),
        "Lot": df["VAL_INLAKH"] * 1e5 / (df["CONTRACTS"] * df["SETTLE_PR"]),
    })


def parse_udiff(path):
    cols = {"TradDt", "FinInstrmTp", "TckrSymb", "XpryDt", "TtlTradgVol", "TtlTrfVal", "OpnIntrst", "NewBrdLotQty"}
    df = _read(path, cols)
    df = df[df["TckrSymb"].isin(SYMBOLS) & df["FinInstrmTp"].isin(["IDF", "IDO"])].copy()
    if df.empty:
        return None
    return pd.DataFrame({
        "Symbol": df["TckrSymb"],
        "Date": pd.to_datetime(df["TradDt"], errors="coerce"),
        "Expiry": pd.to_datetime(df["XpryDt"], errors="coerce"),
        "IsOption": df["FinInstrmTp"] == "IDO",
        "Volume": df["TtlTradgVol"].astype(float),
        "Value": df["TtlTrfVal"].astype(float),
        "OI": df["OpnIntrst"].astype(float),
        "Lot": df["NewBrdLotQty"].astype(float),
    })


def summarise(df):
    df = df.replace([np.inf, -np.inf], np.nan)
    opt = df[df["IsOption"]]
    g = ["Symbol", "Date"]
    out = pd.DataFrame({
        "Value_Total": df.groupby(g)["Value"].sum(),
        "Value_Options": opt.groupby(g)["Value"].sum(),
        "Volume_Options": opt.groupby(g)["Volume"].sum(),
        "OI_Options": opt.groupby(g)["OI"].sum(),
        "OI_Futures": df[~df["IsOption"]].groupby(g)["OI"].sum(),
        "LotSize": df.groupby(g)["Lot"].median(),
    })
    today = opt[opt["Expiry"] == opt["Date"]]
    out["Value_ExpiringToday"] = today.groupby(g)["Value"].sum()
    out["Volume_ExpiringToday"] = today.groupby(g)["Volume"].sum()
    out["NExpiriesListed"] = opt[opt["OI"] > 0].groupby(g)["Expiry"].nunique()
    return out.fillna({"Value_ExpiringToday": 0.0, "Volume_ExpiringToday": 0.0}).reset_index()


def run():
    files = [(p, parse_legacy) for p in sorted(LEGACY_DIR.glob("*.zip"))] + \
            [(p, parse_udiff) for p in sorted(UDIFF_DIR.glob("*.zip"))]
    parts, failed = [], []
    for path, fn in files:
        try:
            d = fn(path)
            if d is not None:
                parts.append(summarise(d))
        except Exception as e:  # keep going, report at end
            failed.append((path.name, str(e)))
    if failed:
        print(f"{len(failed)} files failed, e.g. {failed[:3]}")
    panel = pd.concat(parts, ignore_index=True).sort_values(["Symbol", "Date"]).reset_index(drop=True)
    panel.to_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet", index=False)

    # True expiry dates: days on which expiring option contracts actually traded.
    ex = panel[panel["Value_ExpiringToday"] > 0][["Symbol", "Date"]].rename(columns={"Date": "ExpiryDate"})
    ex["YM"] = ex["ExpiryDate"].dt.to_period("M")
    ex["IsMonthly"] = ex.groupby(["Symbol", "YM"])["ExpiryDate"].transform("max") == ex["ExpiryDate"]
    ex.drop(columns="YM").to_parquet(config.INTERIM_DATA_DIR / "index_expiry_dates.parquet", index=False)
    print(panel.groupby("Symbol")["Date"].agg(["min", "max", "count"]))
    print(ex.groupby("Symbol").agg(n=("ExpiryDate", "size"), monthly=("IsMonthly", "sum")))


if __name__ == "__main__":
    run()
