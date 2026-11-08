"""
Downloads NSE F&O Bhavcopy archives directly (no manual UI clicking needed).

Two formats, split at the NSE format cutover (2024-07-08):
  - Legacy: https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{YYYY}/{MON}/fo{DD}{MON}{YYYY}bhav.csv.zip
  - UDiFF (post-cutover): https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{YYYYMMDD}_F_0000.csv.zip

Skips weekends and NSE holidays (data/raw/nse_holidays.csv). Saves one zip per
trading day into data/raw/fo_bhavcopy/{legacy,udiff}/, skipping files already present
so the script is safely re-runnable/resumable.
"""
import sys
import time
import requests
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from src import config

LEGACY_CUTOVER = date(2024, 7, 8)  # last legacy-format day is 2024-07-05 (Fri); UDiFF starts 2024-07-08 (Mon)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
}

OUT_DIR = config.RAW_DATA_DIR / "fo_bhavcopy"
LEGACY_DIR = OUT_DIR / "legacy"
UDIFF_DIR = OUT_DIR / "udiff"


def load_holidays():
    df = pd.read_csv(config.RAW_DATA_DIR / "nse_holidays.csv")
    date_col = [c for c in df.columns if "date" in c.lower()][0]
    return set(pd.to_datetime(df[date_col]).dt.date)


def trading_days(start, end, holidays):
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            yield d
        d += timedelta(days=1)


def legacy_url(d):
    mon = d.strftime("%b").upper()
    return f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{mon}/fo{d.day:02d}{mon}{d.year}bhav.csv.zip"


def udiff_url(d):
    return f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d.strftime('%Y%m%d')}_F_0000.csv.zip"


def download(session, url, out_path, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200 and len(r.content) > 1000:
                out_path.write_bytes(r.content)
                return True
            elif r.status_code == 404:
                return None  # not found (likely a holiday NSE didn't list, or genuinely no data)
            else:
                time.sleep(1.5)
        except requests.RequestException:
            time.sleep(1.5)
    return False


def run(start_str, end_str):
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    UDIFF_DIR.mkdir(parents=True, exist_ok=True)

    start = pd.to_datetime(start_str).date()
    end = pd.to_datetime(end_str).date()
    holidays = load_holidays()

    session = requests.Session()
    try:
        session.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
    except requests.RequestException:
        pass

    ok, failed, skipped, not_found = 0, [], 0, []
    days = list(trading_days(start, end, holidays))
    print(f"Fetching {len(days)} trading days from {start} to {end}")

    for i, d in enumerate(days, 1):
        if d < LEGACY_CUTOVER:
            url = legacy_url(d)
            out_path = LEGACY_DIR / Path(url).name
        else:
            url = udiff_url(d)
            out_path = UDIFF_DIR / Path(url).name

        if out_path.exists() and out_path.stat().st_size > 1000:
            skipped += 1
            continue

        result = download(session, url, out_path)
        if result is True:
            ok += 1
        elif result is None:
            not_found.append(str(d))
        else:
            failed.append(str(d))

        if i % 50 == 0:
            print(f"  {i}/{len(days)}  ok={ok} skipped={skipped} not_found={len(not_found)} failed={len(failed)}")
        time.sleep(0.15)  # polite rate limit

    print(f"\nDone. ok={ok} skipped(existing)={skipped} not_found={len(not_found)} failed={len(failed)}")
    if not_found:
        print(f"Not found (first 10): {not_found[:10]}")
    if failed:
        print(f"Failed (first 10, retry these): {failed[:10]}")


if __name__ == "__main__":
    start_arg = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
    end_arg = sys.argv[2] if len(sys.argv) > 2 else pd.Timestamp.today().strftime("%Y-%m-%d")
    run(start_arg, end_arg)
