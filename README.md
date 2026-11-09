# Expiry-Day Liquidity Concentration in Indian Index Derivatives

[![Author](https://img.shields.io/badge/Author-Prakash%20Ukhalkar-blue.svg)](https://github.com/prakash-ukhalkar)
[![GitHub Repository](https://img.shields.io/badge/Repo-banknifty--expiry--volatility--ml-lightgrey?logo=github)](https://github.com/prakash-ukhalkar/banknifty-expiry-volatility-ml)
[![Python Version](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Method](https://img.shields.io/badge/Method-Difference--in--Differences-orange.svg)](#)
[![Data](https://img.shields.io/badge/Data-NSE%20Bhavcopy%202020--2026-green.svg)](#)

An empirical capital-markets study of India's National Stock Exchange (NSE) index-derivatives reforms, using a difference-in-differences natural experiment to measure how retiring a weekly options contract concentrates trading activity on the surviving expiry day.

---

## Research question and findings (corrected, Nov 2026)

SEBI's weekly-contract rule (one weekly index-options expiry per exchange) led NSE to retire weekly options on Bank Nifty, Fin Nifty and Midcap Nifty after 13 Nov 2024 while Nifty 50 kept its own; BSE retired Bankex weeklies and kept Sensex. The study measures what this did to trading activity, using true per-index expiry dates taken from the Bhavcopy expiry field (`scripts/build_index_expiry_panel.py`). All effects below are log points from within-exchange difference-in-differences on index-month panels with index-specific linear trends and month-clustered standard errors (Nov 2024 excluded), unless stated otherwise.

* **Activity collapsed rather than concentrated.** Bank Nifty vs Nifty (NSE): total turnover -1.97 (s.e. 0.21), expiry-day turnover in levels -0.62 (0.22), expiry-day *share* of monthly turnover +1.35 (0.11). Bankex vs Sensex (BSE): -4.84 (1.83), -3.82 (2.14) and +1.02 (0.38). The expiry-day share rose from about 14% to 40-50% because ordinary-day turnover collapsed, not because expiry-day turnover rose. Fin Nifty and Midcap Nifty show the same pattern. Specifications without index trends (`did_monthly_true_expiry.json`) give larger magnitudes with the same signs.
* **Calendar and specification matter.** A rule-based expiry calendar misclassifies 8 of 23 post-reform Bank Nifty monthly expiries and 10 of 23 for Nifty, and flips the sign of the expiry-day share effect (+1.35 with true dates, -1.05 with the rule-based calendar; `calendar_sensitivity.json`). Separately, a daily expiry-day-vs-other-day regression is a ratio of ratios and gives a large positive triple interaction (+1.86 even with true dates) although expiry-day turnover fell.
* **Small-sample inference.** With six indices the pooled two-way-FE share effect (+1.51) ranks first of the 15 possible treatment assignments (exact randomization p = 0.067, the minimum attainable); the pooled turnover and level effects are not distinguishable from reassignments (p = 0.20 and 0.33). Treat the pooled results with caution; Nifty and Sensex are contaminated controls.
* **Pre-trends.** Event-study pre-trend coefficients are modest but non-zero. Under a smoothness restriction on the post-period differential trend (Delta^SD(M), `scripts/pretrend_robust_ci.py`), robust 95% confidence intervals for Bank Nifty vs Nifty are share [+1.30, +1.71] at M = 0, total turnover [-2.10, -1.63] and expiry-day level [-0.63, -0.35]. The share and turnover intervals exclude zero up to 0.52x and 0.82x the largest pre-period second difference (M_pre); the expiry-day level result breaks down at 0.10x and should be read as suggestive. Bankex vs Sensex bounds are uninformative (very noisy short pre-period). Identified sets at the point estimates are in `pretrend_sensitivity.json`.
* **Placebo and timing.** Stock F&O (never had weeklies) fell only ~9% (post/pre = 0.91) while Bank Nifty fell ~90% (0.10), Fin Nifty ~99%, Bankex ~97%; Nifty (1.67x) and Sensex (2.54x) rose, so the collapse is not a market-wide shock. In-time placebo cutovers (31 fake dates, pre-period only) give effects far smaller than the true one. A daily dose-response around the transition gives a Bank Nifty-vs-Nifty log turnover gap that rises 0.36 per listed Bank Nifty weekly expiry (p < 1e-5, n = 83). The drop coincides with the Nov-2024 retirement, ahead of the later SEBI measures (verify dates against the circulars).
* **Migration is bounded, not identified.** Six-index turnover is flat (-0.5%) and Nifty plus Sensex gained 99% of the retired indices' lost turnover in raw terms, but both were growing fast before the reform. Assuming 25% or 50% a year of organic growth lowers the migrated share to ~63% and ~21%. Using aggregate stock F&O (growth factor 1.06) as an observed organic-growth benchmark (`scripts/migration_stock_benchmark.py`), the migrated share is 94% if the retained indices would have grown like stock derivatives, 74%, 54% and 15% if they would have grown 1.25, 1.5 and 2 times as fast. Report it as a range.
* **Option-level composition.** Before the reform ~97-100% of index-option turnover was in contracts within 7 days of expiry. After retirement Bank Nifty's 0-7 day share fell to ~71% (vs ~97% for Nifty). ATM Corwin-Schultz/high-low measures are exploratory only (they mostly reflect volatility and price level), so no market-quality claim is made for the options themselves. Market-wide NSE index-options client share moved from 34.1% to 36.4% (pro 58.7% to 56.3%).
* **Futures spillover is null.** Bank Nifty futures Amihud illiquidity (-0.01), Corwin-Schultz spread (~0) and Bankex futures measures show no significant change; Bank Nifty futures intraday range fell ~16%. Option-level spreads, order-book and account-level data are not available, so option market quality and investor outcomes remain untested.
* **Settlement-weekday reforms (re-run on the true calendar).** The interrupted-time-series (1,670 days, 5 outcomes) finds no expiry-week x regime interaction (all p > 0.17), and the 5-fold walk-forward (913 out-of-fold days) finds directional accuracy of 49-52% with every Holm-adjusted p > 0.5. After Nov 2024 the weekday and the weekly-contract status change together, so these regimes cannot separate the two reforms.
* **An earlier version of this repo claimed "expiry-day turnover rose 283%".** That came from a wrong rule-based expiry calendar and a ratio-of-ratios specification; see `results/LEGACY_README.md`. Do not cite those numbers.

Reproduce with `scripts/run_corrected_pipeline.sh`. Small processed panels are in `results/panels/`, and `python -m pytest tests -q` checks the derived panels. Raw exchange files are public and are downloaded by the `download_*` scripts; the large intermediate parquet files are not committed.

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
├── tests/           # Checks on the derived panels
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
