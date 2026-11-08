"""
Contract-level INDEX-OPTION panel (traded contracts only) for the six indices, NSE (Bhavcopy, both formats) + BSE (market summary), and a
daily STOCK-F&O aggregate (never-weekly placebo group).  Parallel over files.
Outputs: data/interim/options_contracts.parquet  (Symbol, Date, Expiry, Strike, Type, O,H,L,C, Settle, Value, Volume, OI, Und)
         data/interim/stock_fo_daily.parquet     (Date, Value_StockOpt, Value_StockFut, OI_StockOpt, OI_StockFut)
Underlying price: UDiFF UndrlygPric / BSE underlying close; for legacy NSE files the same-day near-month futures settle (futures_daily.parquet).
"""
import zipfile
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd
from src import config

NSE = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
LEG = config.RAW_DATA_DIR / "fo_bhavcopy" / "legacy"; UDI = config.RAW_DATA_DIR / "fo_bhavcopy" / "udiff"; BSE = config.RAW_DATA_DIR / "bse_fo"


def _zip(p):
    with zipfile.ZipFile(p) as z, z.open(z.namelist()[0]) as f:
        return pd.read_csv(f)


def parse_legacy(p):
    d = _zip(p)
    d["Date"] = pd.to_datetime(d.TIMESTAMP, format="%d-%b-%Y", errors="coerce")
    s = d[d.INSTRUMENT.isin(["OPTSTK", "FUTSTK"])]
    stock = {"Date": d.Date.iloc[0], "Value_StockOpt": s[s.INSTRUMENT == "OPTSTK"].VAL_INLAKH.sum() * 1e5,
             "Value_StockFut": s[s.INSTRUMENT == "FUTSTK"].VAL_INLAKH.sum() * 1e5,
             "OI_StockOpt": s[s.INSTRUMENT == "OPTSTK"].OPEN_INT.sum(), "OI_StockFut": s[s.INSTRUMENT == "FUTSTK"].OPEN_INT.sum()}
    o = d[(d.INSTRUMENT == "OPTIDX") & d.SYMBOL.isin(NSE) & (d.CONTRACTS > 0)]
    return pd.DataFrame({"Symbol": o.SYMBOL, "Date": o.Date, "Expiry": pd.to_datetime(o.EXPIRY_DT, format="%d-%b-%Y", errors="coerce"),
                         "Strike": o.STRIKE_PR, "Type": o.OPTION_TYP.str[:1], "O": o.OPEN, "H": o.HIGH, "L": o.LOW, "C": o.CLOSE, "Settle": o.SETTLE_PR,
                         "Value": o.VAL_INLAKH * 1e5, "Volume": o.CONTRACTS, "OI": o.OPEN_INT, "Und": np.nan}), stock


def parse_udiff(p):
    d = _zip(p)
    d["Date"] = pd.to_datetime(d.TradDt)
    s = d[d.FinInstrmTp.isin(["STO", "STF"])]
    stock = {"Date": d.Date.iloc[0], "Value_StockOpt": s[s.FinInstrmTp == "STO"].TtlTrfVal.sum(), "Value_StockFut": s[s.FinInstrmTp == "STF"].TtlTrfVal.sum(),
             "OI_StockOpt": s[s.FinInstrmTp == "STO"].OpnIntrst.sum(), "OI_StockFut": s[s.FinInstrmTp == "STF"].OpnIntrst.sum()}
    o = d[(d.FinInstrmTp == "IDO") & d.TckrSymb.isin(NSE) & (d.TtlTradgVol > 0)]
    return pd.DataFrame({"Symbol": o.TckrSymb, "Date": o.Date, "Expiry": pd.to_datetime(o.XpryDt), "Strike": o.StrkPric, "Type": o.OptnTp.str[:1],
                         "O": o.OpnPric, "H": o.HghPric, "L": o.LwPric, "C": o.ClsPric, "Settle": o.SttlmPric, "Value": o.TtlTrfVal,
                         "Volume": o.TtlTradgVol, "OI": o.OpnIntrst, "Und": o.UndrlygPric}), stock


def parse_bse(p):
    cols = list(pd.read_csv(BSE / "MS_20250115.csv", nrows=0).columns)
    x = pd.read_csv(p)
    if "Product Type" not in x.columns:
        x = pd.read_csv(p, header=None, names=cols)
    x = x[(x["Product Type"] == "IO") & x["Asset Code"].isin(["BSX", "BKX"]) & (x["Total Traded Quantity"] > 0)]
    return pd.DataFrame({"Symbol": x["Asset Code"].map({"BSX": "SENSEX", "BKX": "BANKEX"}),
                         "Date": pd.to_datetime(x["Market Summary Date"], format="%d %b %Y", errors="coerce"),
                         "Expiry": pd.to_datetime(x["Expiry Date"], format="%d %b %Y", errors="coerce"), "Strike": x["Strike Price"],
                         "Type": x["Option Type (Call/Put)"].astype(str).str[:1], "O": x["Open Price"], "H": x["High Price"], "L": x["Low Price"],
                         "C": x["Close Price"], "Settle": x["Close Price"], "Value": x["Total Traded Value (in Thousands)(absolute)"] * 1000.0,
                         "Volume": x["Total Traded Quantity"], "OI": x["Open Interest"], "Und": x["Underlying Asset Close Price"]}), None


def work(job):
    kind, p = job
    try:
        return {"leg": parse_legacy, "udi": parse_udiff, "bse": parse_bse}[kind](p)
    except Exception as e:
        return (None, None)


if __name__ == "__main__":
    jobs = [("leg", p) for p in sorted(LEG.glob("*.zip"))] + [("udi", p) for p in sorted(UDI.glob("*.zip"))] + [("bse", p) for p in sorted(BSE.glob("MS_*.csv"))]
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(work, jobs, chunksize=8))
    opts = pd.concat([r[0] for r in res if r[0] is not None and len(r[0])], ignore_index=True)
    stock = pd.DataFrame([r[1] for r in res if r[1] is not None]).sort_values("Date").drop_duplicates("Date")
    fut = pd.read_parquet(config.INTERIM_DATA_DIR / "futures_daily.parquet")[["Symbol", "Date", "Settle"]].rename(columns={"Settle": "FutSettle"})
    opts = opts.merge(fut, on=["Symbol", "Date"], how="left")
    opts["Und"] = opts.Und.fillna(opts.FutSettle)
    opts = opts.drop(columns="FutSettle").dropna(subset=["Expiry", "Strike"])
    for c in ["O", "H", "L", "C", "Settle", "Value", "Volume", "OI", "Und", "Strike"]:
        opts[c] = opts[c].astype("float32") if c not in ("Value",) else opts[c]
    opts.to_parquet(config.INTERIM_DATA_DIR / "options_contracts.parquet", index=False)
    stock.to_parquet(config.INTERIM_DATA_DIR / "stock_fo_daily.parquet", index=False)
    print(len(opts), opts.groupby("Symbol").size().to_dict(), "stock days", len(stock))
