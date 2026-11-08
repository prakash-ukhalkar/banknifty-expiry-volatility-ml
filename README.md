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
* **Cross-exchange replication (BSE).** BSE kept Sensex weeklies and retired Bankex weeklies. Within-exchange DiDs agree in sign on both exchanges (log points): total turnover -1.97 (NSE, Bank Nifty vs Nifty) and -4.84 (BSE, Bankex vs Sensex); expiry-day share +1.35 and +1.02. The pooled two-way-FE share effect (+1.51) ranks first of the 15 possible treatment assignments (exact randomization p = 0.067, the minimum attainable with 6 indices); the turnover effects are not distinguishable from reassignments (p = 0.20 and 0.33).
* **Substitution is not point-identified.** Six-index turnover is flat (-0.5%) and Nifty plus Sensex gained 99% of the treated indices' lost turnover in raw terms, but both controls were growing fast before the reform, so the substitution share falls to ~63% at 25%/yr and ~21% at 50%/yr assumed organic growth. Report it as a range.
* **Market quality (futures spillover) is null.** Bank Nifty futures Amihud illiquidity (-0.01), Corwin-Schultz spread (~0) and Bankex futures measures show no significant change; Bank Nifty futures intraday range fell ~16%. Option-level spreads and order-book data are not available, so option market quality remains untested. Market-wide NSE index-option client share rose from 34.1% to 36.4% (pro 58.7% to 56.3%).
* **Placebo and timing.** Stock F&O (never had weeklies) fell only ~9% (post/pre = 0.91) while Bank Nifty fell ~90% (0.10), FINNIFTY ~99%, Bankex ~97%; Nifty (1.67x) and Sensex (2.54x) rose. So the collapse is not a market-wide shock. A daily dose-response around the transition gives a Bank Nifty-vs-Nifty log turnover gap that rises 0.36 per listed Bank Nifty weekly expiry (p < 1e-5, n = 83). The drop coincides with the Nov-2024 retirement, ahead of the Feb-2025 SEBI measures (verify dates against the circulars).
* **Option-level composition.** Pre-reform ~97-100% of index-option turnover was in contracts within 7 days of expiry. After retirement Bank Nifty's 0-7 day share fell to ~71% (vs ~97% for Nifty). ATM Corwin-Schultz/high-low measures are exploratory only (they mostly reflect volatility and price level), so no market-quality claim is made for the options themselves.
* **An earlier version of this repo claimed "expiry-day turnover rose 283%".** That came from a wrong rule-based expiry calendar and a ratio-of-ratios specification; see `results/LEGACY_README.md`. Do not cite those numbers.
* **Settlement-weekday reforms (re-run on the true calendar):** the interrupted-time-series (1,670 days, 5 outcomes) finds no expiry-week x regime interaction (all p > 0.17), and the 5-fold walk-forward (913 out-of-fold days) finds directional accuracy of 49-52% with every Holm-adjusted p > 0.5. Caveat: after Nov 2024 the weekday and the weekly-contract status change together, so these regimes cannot separate the two reforms.

Reproduce with `scripts/run_corrected_pipeline.sh`; small processed panels are in `results/panels/` and `python -m pytest tests -q` checks the derived panels.

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
