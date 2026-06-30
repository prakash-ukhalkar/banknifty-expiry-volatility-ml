# Bank Nifty Predictability Under Regulatory Expiry-Structure Reform

This project analyzes the impact of regulatory derivatives expiry-structure reforms on Bank Nifty index predictability. 

We test the hypothesis that explicitly encoding expiry-cycle mechanics (days to next expiry, expiry-week indicators) and volatility regimes (via a Hidden Markov Model) yields superior next-day forecasting compared to standard baseline models using only typical technical indicators.

## Project Structure

```
banknifty-expiry-volatility-ml/
│
├── data/
│   ├── raw/                          # untouched downloads (yfinance ^NSEBANK, calendars)
│   ├── interim/                      # cleaned, un-engineered data
│   └── processed/                    # train/val/test splits with features
│
├── notebooks/                        # step-by-step analysis notebooks (01 to 09)
│
├── src/                              # reusable Python module
│   ├── config.py                     # paths, settings, random seed
│   ├── data_loader.py                # raw data fetch and calendar merge
│   ├── features.py                   # indicator and cyclical expiry engineering
│   ├── regime_detection.py           # volatility regime identification
│   ├── models.py                     # predictive models (XGBoost, LSTMs)
│   ├── evaluation.py                 # Diebold-Mariano test & evaluation metrics
│   └── plotting.py                   # matplotlib styling
│
├── models/                           # saved model artifacts
├── results/                          # output figures and tables
└── manuscript/                       # paper draft and checklists
```

## Setup and Usage

### Environment Setup
A virtual environment `bn_venv` is configured at the workspace root. To activate and install dependencies:

```powershell
# In PowerShell:
..\bn_venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Running the Notebooks
Start Jupyter Lab/Notebook and navigate through the notebooks in numerical order to run the pipeline.
