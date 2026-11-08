"""
Builds the Nifty 50 F&O volume/OI panel from the SAME downloaded Bhavcopy archive
used for Bank Nifty (scripts/download_fo_bhavcopy.py already pulled every F&O
symbol, not just BANKNIFTY -- no new download needed). Reuses the shared
parse_legacy_file/parse_udiff_file/aggregate_daily from build_fo_volume_oi_dataset.py
with symbol="NIFTY" so both datasets go through identical, maintained logic.

Nifty 50 is the control group for the weekly-options-discontinuation natural
experiment: SEBI's single-weekly-index-derivative-per-exchange rule forced NSE
to pick ONE index to keep weekly options on, and it kept NIFTY (not BANKNIFTY).
So Nifty 50 should show no (or a much weaker) analogous Nov-2024 concentration
shift -- if it showed an equally large one, that would suggest the Bank Nifty
result is driven by something market-wide rather than the weekly-options removal.
"""
import pandas as pd

from src import config
from scripts.build_fo_volume_oi_dataset import (
    LEGACY_DIR, UDIFF_DIR, parse_legacy_file, parse_udiff_file, aggregate_daily,
)

SYMBOL = "NIFTY"


def run():
    legacy_files = sorted(LEGACY_DIR.glob("*.zip"))
    udiff_files = sorted(UDIFF_DIR.glob("*.zip"))
    print(f"Found {len(legacy_files)} legacy files, {len(udiff_files)} UDiFF files")

    frames = []
    failed = []
    for path in legacy_files:
        try:
            parsed = parse_legacy_file(path, symbol=SYMBOL)
            if parsed is not None:
                frames.append(parsed)
        except Exception as e:
            failed.append((path.name, str(e)))
    for path in udiff_files:
        try:
            parsed = parse_udiff_file(path, symbol=SYMBOL)
            if parsed is not None:
                frames.append(parsed)
        except Exception as e:
            failed.append((path.name, str(e)))

    if failed:
        print(f"Failed to parse {len(failed)} files, e.g.: {failed[:5]}")

    combined = pd.concat(frames, ignore_index=True)
    daily = aggregate_daily(combined)

    out_path = config.INTERIM_DATA_DIR / "nifty_fo_volume_oi.parquet"
    daily.to_parquet(out_path, index=False)
    print(f"\nSaved {len(daily)} daily rows to {out_path}")
    print(f"Date range: {daily['Date'].min().date()} to {daily['Date'].max().date()}")


if __name__ == "__main__":
    run()
