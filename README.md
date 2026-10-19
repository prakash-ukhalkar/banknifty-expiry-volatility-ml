# Expiry-Day Liquidity Concentration in Indian Index Derivatives

[![Author](https://img.shields.io/badge/Author-Prakash%20Ukhalkar-blue.svg)](https://github.com/prakash-ukhalkar)
[![GitHub Repository](https://img.shields.io/badge/Repo-banknifty--expiry--volatility--ml-lightgrey?logo=github)](https://github.com/prakash-ukhalkar/banknifty-expiry-volatility-ml)
[![Python Version](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Method](https://img.shields.io/badge/Method-Difference--in--Differences-orange.svg)](#)
[![Data](https://img.shields.io/badge/Data-NSE%20Bhavcopy%202020--2026-green.svg)](#)

An empirical capital-markets study of India's National Stock Exchange (NSE) index-derivatives reforms, using a difference-in-differences natural experiment to measure how retiring a weekly options contract concentrates trading activity on the surviving expiry day.

---

## Research question and finding

Two regulatory reforms hit NSE's index-derivatives market within an eighteen-month window:

1. **Settlement-weekday shift** — the weekly index-options expiry moved from Thursday to Wednesday (March 2024) to Tuesday (September 2025).
2. **Single-weekly-contract rule** — a separate rule limiting each exchange to one weekly index-derivatives contract forced NSE to discontinue **Bank Nifty** weekly options (last traded 13 November 2024) while **Nifty 50** retained its own.

This project asks two questions about those reforms and answers both honestly, including the one that came back null:

> **Primary finding:** Using the complete NSE futures-and-options Bhavcopy archive (2020–2026), reconstructed into lot-size-invariant turnover and open-interest series, a difference-in-differences model against the Nifty 50 control finds Bank Nifty's expiry-day trading turnover rose by an additional **283%** (p < 0.001) and open interest by **28%** (p = 0.013) after the weekly-contract removal. The result survives a lot-size confound correction, placebo cutover dates, leave-one-out exclusion of each treated expiry, and an event-study specification confirming a discrete post-reform jump rather than a continuation of a pre-existing trend.
>
> **Secondary finding (null, reported transparently):** A leakage-free walk-forward evaluation and an interrupted-time-series analysis find **no robust evidence** that the settlement-weekday reforms created exploitable next-day return predictability or shifted expiry-week volatility.

The reform's measurable effect operates through **trading concentration**, not price predictability, with direct implications for how exchanges and clearing corporations calibrate settlement-day margining and operational capacity when retiring a derivatives contract.

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
