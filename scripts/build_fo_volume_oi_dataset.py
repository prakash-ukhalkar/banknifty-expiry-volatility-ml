"""
Parses the downloaded NSE F&O Bhavcopy archive (scripts/download_fo_bhavcopy.py output)
into a single daily Bank Nifty derivatives volume/OI panel, spanning the legacy
(pre 2024-07-08) and UDiFF (post) formats.

Legacy columns:  INSTRUMENT, SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, CONTRACTS,
                 VAL_INLAKH, OPEN_INT, CHG_IN_OI, TIMESTAMP
UDiFF columns:   FinInstrmTp (IDF/IDO/STF/STO), TckrSymb, XpryDt, StrkPric, OptnTp,
                 TtlTradgVol, TtlTrfVal, OpnIntrst, ChngInOpnIntrst, TradDt

Output: one row per trading day with total Bank Nifty F&O volume (contracts) and
total open interest, split by instrument type (futures vs. options), so the
expiry-day abnormal-volume/OI event study (Vipul 2005 replication) and the
regime-reform natural experiment can both be built directly on top.
"""
import zipfile
import numpy as np
import pandas as pd

from src import config

LEGACY_DIR = config.RAW_DATA_DIR / "fo_bhavcopy" / "legacy"
UDIFF_DIR = config.RAW_DATA_DIR / "fo_bhavcopy" / "udiff"
SYMBOL = "BANKNIFTY"


def read_zip_csv(path):
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            return pd.read_csv(f)


def parse_legacy_file(path, symbol=SYMBOL):
    """
    Legacy Bhavcopy columns: VAL_INLAKH is traded VALUE in lakhs of rupees --
    lot-size-invariant, unlike CONTRACTS (a lot-size change mechanically shifts
    how many contracts a given rupee turnover implies). Also derives an implied
    lot size per contract-row (Value / (Contracts * SettlePrice)) so OpenInterest
    (which IS in contracts) can be notional-adjusted later -- legacy files have
    no explicit lot-size column, unlike UDiFF's NewBrdLotQty.
    """
    df = read_zip_csv(path)
    df = df[df["SYMBOL"] == symbol].copy()
    if df.empty:
        return None
    df["Date"] = pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y", errors="coerce")
    if df["Date"].isna().all():
        df["Date"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df["IsFuture"] = df["INSTRUMENT"].astype(str).str.startswith("FUT")
    df["Volume"] = df["CONTRACTS"]
    df["Value"] = df["VAL_INLAKH"] * 100000.0  # lakhs -> rupees
    df["OpenInterest"] = df["OPEN_INT"]
    df["ChgOpenInterest"] = df["CHG_IN_OI"]
    with np.errstate(divide="ignore", invalid="ignore"):
        implied_lot = df["Value"] / (df["CONTRACTS"] * df["SETTLE_PR"])
    df["ImpliedLotSize"] = implied_lot.replace([np.inf, -np.inf], np.nan)
    return df[["Date", "IsFuture", "Volume", "Value", "OpenInterest", "ChgOpenInterest", "ImpliedLotSize"]]


def parse_udiff_file(path, symbol=SYMBOL):
    """UDiFF: TtlTrfVal is traded VALUE already in rupees (not lakhs). NewBrdLotQty
    is the exchange-published lot size for that day -- used directly, no need to imply it."""
    df = read_zip_csv(path)
    df = df[df["TckrSymb"] == symbol].copy()
    df = df[df["FinInstrmTp"].isin(["IDF", "IDO"])].copy()
    if df.empty:
        return None
    df["Date"] = pd.to_datetime(df["TradDt"], errors="coerce")
    df["IsFuture"] = df["FinInstrmTp"] == "IDF"
    df["Volume"] = df["TtlTradgVol"]
    df["Value"] = df["TtlTrfVal"]
    df["OpenInterest"] = df["OpnIntrst"]
    df["ChgOpenInterest"] = df["ChngInOpnIntrst"]
    df["ImpliedLotSize"] = df["NewBrdLotQty"]
    return df[["Date", "IsFuture", "Volume", "Value", "OpenInterest", "ChgOpenInterest", "ImpliedLotSize"]]


def aggregate_daily(df):
    """
    Collapse per-contract rows to one row per day: total volume/OI/value,
    futures vs. options, plus a per-day representative lot size (median across
    that day's contracts) used to compute lot-size-invariant notional OI
    (OpenInterest_contracts * LotSize). Bank Nifty's lot size changed 15->30
    right around the same Nov-2024 window as the weekly-options discontinuation
    (confirmed directly in the UDiFF NewBrdLotQty column), so raw contract-count
    OpenInterest is NOT directly comparable across that boundary without this
    adjustment -- Value (rupee turnover) is naturally lot-size-invariant and
    needs no adjustment.
    """
    daily = df.groupby(["Date", "IsFuture"]).agg(
        Volume=("Volume", "sum"),
        Value=("Value", "sum"),
        OpenInterest=("OpenInterest", "sum"),
        ChgOpenInterest=("ChgOpenInterest", "sum"),
        LotSize=("ImpliedLotSize", "median"),
    ).reset_index()

    wide = daily.pivot(index="Date", columns="IsFuture", values=["Volume", "Value", "OpenInterest", "ChgOpenInterest", "LotSize"])
    wide.columns = [
        f"{metric}_{'Futures' if is_fut else 'Options'}"
        for metric, is_fut in wide.columns
    ]
    wide = wide.reset_index()
    for col in wide.columns:
        if col != "Date" and not col.startswith("LotSize"):
            wide[col] = wide[col].fillna(0).astype(float)

    wide["Total_Volume"] = wide.get("Volume_Futures", 0) + wide.get("Volume_Options", 0)
    wide["Total_Value"] = wide.get("Value_Futures", 0) + wide.get("Value_Options", 0)
    wide["Total_OpenInterest"] = wide.get("OpenInterest_Futures", 0) + wide.get("OpenInterest_Options", 0)
    # Representative lot size for the day: prefer the futures lot (single, liquid,
    # least noisy), fall back to the options-implied lot size if futures missing.
    wide["LotSize"] = wide.get("LotSize_Futures").combine_first(wide.get("LotSize_Options"))
    wide["Total_OpenInterest_Notional"] = wide["Total_OpenInterest"] * wide["LotSize"]
    return wide.sort_values("Date").reset_index(drop=True)


def run():
    legacy_files = sorted(LEGACY_DIR.glob("*.zip"))
    udiff_files = sorted(UDIFF_DIR.glob("*.zip"))
    print(f"Found {len(legacy_files)} legacy files, {len(udiff_files)} UDiFF files")

    frames = []
    failed = []
    for path in legacy_files:
        try:
            parsed = parse_legacy_file(path)
            if parsed is not None:
                frames.append(parsed)
        except Exception as e:
            failed.append((path.name, str(e)))
    for path in udiff_files:
        try:
            parsed = parse_udiff_file(path)
            if parsed is not None:
                frames.append(parsed)
        except Exception as e:
            failed.append((path.name, str(e)))

    if failed:
        print(f"Failed to parse {len(failed)} files, e.g.: {failed[:5]}")

    if not frames:
        print("No data parsed -- check that download_fo_bhavcopy.py has populated data/raw/fo_bhavcopy/")
        return

    combined = pd.concat(frames, ignore_index=True)
    daily = aggregate_daily(combined)

    out_path = config.INTERIM_DATA_DIR / "banknifty_fo_volume_oi.parquet"
    daily.to_parquet(out_path, index=False)
    print(f"\nSaved {len(daily)} daily rows to {out_path}")
    print(f"Date range: {daily['Date'].min().date()} to {daily['Date'].max().date()}")
    print(daily.describe())


if __name__ == "__main__":
    run()
