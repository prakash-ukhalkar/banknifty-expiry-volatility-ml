# Expiry-Day Liquidity Concentration in Indian Index Derivatives

[![Author](https://img.shields.io/badge/Author-Prakash%20Ukhalkar-blue.svg)](https://github.com/prakash-ukhalkar)
[![GitHub Repository](https://img.shields.io/badge/Repo-banknifty--expiry--volatility--ml-lightgrey?logo=github)](https://github.com/prakash-ukhalkar/banknifty-expiry-volatility-ml)
[![Python Version](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Method](https://img.shields.io/badge/Method-Difference--in--Differences-orange.svg)](#)
[![Data](https://img.shields.io/badge/Data-NSE%20Bhavcopy%202020--2026-green.svg)](#)

An empirical capital-markets study of India's National Stock Exchange (NSE) index-derivatives reforms, using a difference-in-differences natural experiment to measure how retiring a weekly options contract concentrates trading activity on the surviving expiry day.

---

## Research question and finding (corrected, Nov 2026)

NSE's weekly-contract rule (one weekly index contract per exchange) retired the weekly options on Bank Nifty, Fin Nifty and Midcap Nifty after 13 Nov 2024 while Nifty 50 kept its own. Using true per-index expiry dates taken from the Bhavcopy expiry field (`scripts/build_index_expiry_panel.py`):

* **Activity collapsed rather than concentrated.** Bank Nifty's monthly F&O turnover fell ~94% relative to Nifty (DiD, log points -2.82), its monthly-expiry-day turnover fell ~76% (-1.42), while the expiry day's *share* of the month's turnover rose from ~14% to 40-50% (+1.40 log points). Fin Nifty and Midcap Nifty show the same pattern.
* **Partial substitution to Nifty.** Nifty's rise absorbs roughly 37% of the delisted indices' lost turnover (Nifty's own organic growth was large, so this is an upper bound). Four-index turnover fell ~38%.
* **Design checks.** In-time placebo cutovers (31 fake dates, pre-period only) give effects within +/-0.5 log points versus -2.8 (true); BN-only before/after and window sensitivity agree in sign. Caveat: Nifty is a contaminated control, there are only 3 treated indices, and pre-trend coefficients in the event study are modest but non-zero.
* **An earlier version of this repo claimed "expiry-day turnover rose 283%".** That came from a wrong rule-based expiry calendar and a ratio-of-ratios specification; see `results/LEGACY_README.md`. Do not cite those numbers.
* **Settlement-weekday reforms:** walk-forward and interrupted-time-series analyses find no robust return predictability or volatility shift (secondary result; the ITS used the old calendar and should be re-run).

Reproduce with `scripts/run_corrected_pipeline.sh`.

---

## Project history

This repository originally tested a different hypothesis: whether expiry-calendar and volatility-regime features improve next-day return prediction. Further work found that the project's real, data-verified finding was never about return prediction at all, it was about trading-volume concentration following the weekly-contract removal. The codebase was rebuilt around that finding rather than patched around the original one. The old next-day-prediction result is retained as the honestly-reported secondary null result described above, not as the project's main contribution.

---

## Repository structure

```text
banknifty-expiry-volatility-ml/
│
├── data/            # Raw, intermediate, and processed market data
├── models/          # Saved model checkpoints
├── notebooks/       # Interactive, numbered walkthrough of the full pipeline
├── results/         # Figures, tables, and result files
├── src/             # Reusable core modules (data loading, features, evaluation)
├── scripts/         # Analysis pipeline entry points
└── requirements.txt
```

---

## Setup and installation

### Prerequisites
- Python 3.9, 3.10, or 3.11
- Pip package manager

### Environment configuration
1. **Clone the repository:**
   ```bash
   git clone https://github.com/prakash-ukhalkar/banknifty-expiry-volatility-ml.git
   cd banknifty-expiry-volatility-ml
   ```

2. **Create and activate a virtual environment:**
   *On Windows (PowerShell):*
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   *On Linux/macOS:*
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## Reproducing the analysis

The `scripts/` modules form the canonical pipeline, covering data collection, feature and panel construction, the primary analysis, secondary robustness checks, and figure generation, in that order. `notebooks/` provides a numbered, interactive walkthrough of the same pipeline for anyone who prefers to step through it cell by cell rather than run scripts directly.

---

## Authors & contributors

* **Prakash Ukhalkar** — [@prakash-ukhalkar](https://github.com/prakash-ukhalkar)

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---
<p align="center"><i>An empirical market-microstructure study of NSE index-derivatives reform, built around a natural experiment rather than a predictive-modeling claim.</i></p>
