"""
Downloads (public files, polite 4-thread fetch with retries; skips files already on disk):
  1. BSE derivatives market summary  MS_YYYYMMDD-01.csv  -> data/raw/bse_fo/        (Sensex / Bankex F&O)
  2. NSE participant-wise F&O volume fao_participant_vol_DDMMYYYY.csv -> data/raw/nse_participant/
  3. NSE participant-wise F&O open interest fao_participant_oi_DDMMYYYY.csv -> data/raw/nse_participant/
Trading days = days present in the NSE index panel (data/interim/index_expiry_panel.parquet).
"""
import time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests
from src import config

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BSE_DIR = config.RAW_DATA_DIR / "bse_fo"; PART_DIR = config.RAW_DATA_DIR / "nse_participant"
BSE_DIR.mkdir(parents=True, exist_ok=True); PART_DIR.mkdir(parents=True, exist_ok=True)


def fetch(job):
    url, path, hdr = job
    if path.exists() and path.stat().st_size > 200:
        return "skip"
    for attempt in range(4):
        try:
            r = requests.get(url, headers={**UA, **hdr}, timeout=30)
            if r.status_code == 200 and len(r.content) > 200 and b"<html" not in r.content[:200].lower():
                path.write_bytes(r.content); return "ok"
            if r.status_code in (403, 404) or (r.status_code == 200):
                return f"none{r.status_code}"
        except Exception:
            time.sleep(2 * (attempt + 1))
    return "fail"


def run():
    dates = pd.to_datetime(pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet").Date.unique())
    jobs = []
    for d in sorted(dates):
        jobs.append((f"https://www.bseindia.com/download/Bhavcopy/Derivative/MS_{d:%Y%m%d}-01.csv", BSE_DIR / f"MS_{d:%Y%m%d}.csv", {"Referer": "https://www.bseindia.com/"}))
        for kind in ("vol", "oi"):
            jobs.append((f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_{kind}_{d:%d%m%Y}.csv", PART_DIR / f"{kind}_{d:%Y%m%d}.csv", {}))
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(fetch, jobs))
    print(pd.Series(res).value_counts())


if __name__ == "__main__":
    run()
