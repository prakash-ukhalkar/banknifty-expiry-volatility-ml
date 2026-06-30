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

# Date range for the study (mid-2023 to present)
START_DATE = "2023-06-01"
END_DATE = "2026-06-27"  # Current local date

# Ensure output directories exist
for path in [RAW_DATA_DIR, INTERIM_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR, TABLES_DIR, FIGURES_DIR]:
    path.mkdir(parents=True, exist_ok=True)
