import os
from pathlib import Path

# Base directory paths
SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent

DATA_DIR = PROJECT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

MODELS_DIR = PROJECT_DIR / "models"
RESULTS_DIR = PROJECT_DIR / "results"
TABLES_DIR = RESULTS_DIR / "tables"
FIGURES_DIR = RESULTS_DIR / "figures"

# Project Configuration
RANDOM_SEED = 42

# Date range for the study. Extended back to 2020 so the Thursday-expiry-era
# baseline (pre-March-2024 reform) has enough history to power the regime-shift
# interrupted-time-series analysis -- the original mid-2023 start left only ~8
# months of pre-reform data.
START_DATE = "2020-01-01"
END_DATE = "2026-10-18"  # Current local date

# Ensure output directories exist
for path in [RAW_DATA_DIR, INTERIM_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR, TABLES_DIR, FIGURES_DIR]:
    path.mkdir(parents=True, exist_ok=True)
