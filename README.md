# Bank Nifty Predictability Under Regulatory Expiry-Structure Reform

[![Author](https://img.shields.io/badge/Author-Prakash%20Ukhalkar-blue.svg)](https://github.com/prakash-ukhalkar)
[![GitHub Repository](https://img.shields.io/badge/Repo-banknifty--expiry--volatility--ml-lightgrey?logo=github)](https://github.com/prakash-ukhalkar/banknifty-expiry-volatility-ml)
[![Python Version](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ML Pipeline](https://img.shields.io/badge/Pipeline-Machine%20Learning-orange.svg)](#)
[![HMM Volatility](https://img.shields.io/badge/Regimes-Hidden%20Markov%20Models-green.svg)](#)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](#)

An advanced machine learning and quantitative research pipeline designed to analyze and forecast the predictability of the **Bank Nifty (NSE: NIFTYBANK)** index under regulatory derivatives expiry-structure reforms.

---

## 📌 Project Overview & Research Hypothesis

Regulatory shifts in derivatives contracts (e.g., changes in weekly/monthly expiry cycles, contract sizing, and trading calendars) significantly impact market liquidity dynamics, volatility clusters, and index predictability. 

This project implements and tests the following research hypothesis:
> **Hypothesis:** *Explicitly encoding cyclical expiry-cycle mechanics (days to next expiry, expiry-week indicators) and volatility regimes (detected via a Hidden Markov Model) yields statistically superior next-day forecasting compared to standard baseline models utilizing only typical technical indicators.*

### 🛠️ Key Methodology Components
1. **Regime Detection**: A Gaussian Hidden Markov Model (HMM) trained on index returns and intraday volatility ranges to classify the market state into distinct volatility regimes (e.g., Low, Medium, High).
2. **Cyclical Feature Engineering**: Cyclical mapping of days to next contract expiry using sine/cosine transformations to represent the proximity of derivative expirations.
3. **Predictive Modeling**: Comparison between classical baselines and advanced machine learning models (XGBoost, LSTM architectures).
4. **Statistical Significance**: Robust model comparison using the **Diebold-Mariano (DM) test** to verify if the predictive improvements of the proposed models are statistically significant.

---

## 📂 Repository Structure

The codebase is structured to ensure modularity, scalability, and reproducibility. Uncommitted local files (such as local database cache, virtual environments, manuscript drafts, and temporary scripts) are excluded, leaving the following core structure:

```text
banknifty-expiry-volatility-ml/
│
├── data/                             # Data directory placeholders (git-ignored raw data)
│   ├── raw/                          # Placeholder for raw downloads (e.g., NSEBANK data, trading calendars)
│   ├── interim/                      # Placeholder for cleaned, un-engineered datasets
│   └── processed/                    # Placeholder for engineered train/val/test splits
│
├── models/                           # Saved model checkpoints and serialized artifacts
│
├── notebooks/                        # Jupyter notebooks for step-by-step pipeline execution
│   ├── 01_data_collection.ipynb      # Market data download and trading calendar acquisition
│   ├── 02_data_cleaning_eda.ipynb    # Data alignment, missing value resolution, and initial EDA
│   ├── 03_feature_engineering.ipynb  # Indicator calculations and cyclical expiry features
│   ├── 04_volatility_regime_detection.ipynb # HMM training and volatility state labeling
│   ├── 05_baseline_models.ipynb      # Implementation of baseline models using technical indicators
│   ├── 06_proposed_model.ipynb       # proposed model development (regimes + expiry features)
│   ├── 07_ablation_study.ipynb       # Systematically isolating feature set contributions
│   ├── 08_evaluation_and_diagnostics.ipynb # Performance diagnostics and statistical testing
│   └── 09_figures_for_paper.ipynb    # Publication-ready figure and table generations
│
├── results/                          # Output folders for evaluation records
│   ├── figures/                      # Generated performance plots, ROC curves, and visualizations
│   └── tables/                       # Serialized LaTeX and Markdown summary tables
│
├── src/                              # Reusable core Python package modules
│   ├── __init__.py                   # Package initialization
│   ├── config.py                     # Paths, global settings, constants, and random seeds
│   ├── data_loader.py                # Functions to load and align dataset inputs
│   ├── features.py                   # Technical indicator computations and cyclical conversions
│   ├── regime_detection.py           # Gaussian Hidden Markov Model wrapper
│   ├── models.py                     # XGBoost and LSTM model specifications and wrappers
│   ├── evaluation.py                 # Diebold-Mariano test and forecasting evaluation metrics
│   └── plotting.py                   # Consolidated plotting style guidelines and theme settings
│
└── requirements.txt                  # Consolidated Python package dependencies
```

*Note: The actual data files in `data/`, model checkpoints in `models/`, and generated outputs in `results/` are git-ignored to prevent bloating. Empty folders are tracked using `.gitkeep` files.*

---

## ⚙️ Setup and Installation

### Prerequisites
- Python 3.9, 3.10, or 3.11
- Pip package manager

### Environment Configuration
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

## 🚀 Execution Pipeline

To run the analysis, execute the notebooks inside the `notebooks/` directory sequentially:

1. **`01_data_collection`**: Fetches daily and intraday asset history for the Bank Nifty index alongside expiry calendars.
2. **`02_data_cleaning_eda`**: Merges datasets, handles holiday adjustments, and performs initial summary statistics.
3. **`03_feature_engineering`**: Generates rolling technical indicators and calculates cyclical distances to next expiry events.
4. **`04_volatility_regime_detection`**: Builds and optimizes a Gaussian HMM to extract hidden volatility states.
5. **`05_baseline_models`**: Standard predictive modeling using only traditional technical features.
6. **`06_proposed_model`**: Combined architecture integrating HMM states and cyclic expiry indicators.
7. **`07_ablation_study`**: Isolates the performance gains attributable to expiry cycle features versus volatility regimes.
8. **`08_evaluation_and_diagnostics`**: Calculates final metrics and performs Diebold-Mariano tests.
9. **`09_figures_for_paper`**: Generates the final high-resolution plots and LaTeX tables.

---

## 👥 Authors & Contributors

*   **Prakash Ukhalkar**
    *   **GitHub:** [@prakash-ukhalkar](https://github.com/prakash-ukhalkar)

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---
<p align="center"><i>Developed for quantitative research and machine learning applications in financial markets.</i></p>
