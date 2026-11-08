"""
Builds the notebooks/ sequence from scratch to mirror the CURRENT analysis
pipeline (F&O Bhavcopy ingestion, lot-size-invariant construction, the
difference-in-differences primary result, its robustness checks, and the
honest-null secondary predictability/volatility analyses). This replaces the
old nine notebooks, which documented the original, now-superseded,
next-day-return-prediction study.

Each notebook orchestrates calls into the real, tested modules in src/ and
scripts/ rather than re-implementing logic, so there is a single source of
truth. Heavy one-time steps (the full NSE Bhavcopy download, the five-fold
walk-forward refit) are documented with the exact command to reproduce them
rather than re-run inside the notebook, to keep notebook execution fast;
everything else runs live against the cached intermediate/results files.

Usage:
    python -m scripts.build_notebooks
"""
from pathlib import Path
import nbformat as nbf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NB_DIR = PROJECT_ROOT / "notebooks"

PIPELINE_INDEX = """
1. **01_data_collection.ipynb** -- index OHLCV, F&O Bhavcopy archive (NOTE: the rule-based expiry calendar it builds is NOT used for inference)
2. **02_feature_engineering_and_fo_construction.ipynb** -- technical features (true-calendar expiry features) and the true-expiry index panel
3. **03_weekly_options_discontinuation_identification.ipynb** -- true expiry dates per index and a calendar audit
4. **04_primary_diff_in_diff_analysis.ipynb** -- corrected symbol-month DiD (turnover, expiry-day turnover, expiry-day share)
5. **05_robustness_checks.ipynb** -- placebo, window sensitivity, substitution range, participant mix, futures market quality
6. **06_expiry_volume_event_study.ipynb** -- expiry-day concentration for six NSE/BSE indices
7. **07_walk_forward_predictability.ipynb** -- secondary: leakage-free predictability test on the true calendar (null)
8. **08_interrupted_time_series.ipynb** -- secondary: settlement-weekday ITS plus clean weekday-only contrasts (null)
9. **09_figures_for_paper.ipynb** -- displays the corrected figures
10. **10_option_microstructure_and_placebo.ipynb** -- option-level outcomes, stock-F&O placebo, dose-response
""".strip()


def header_cell(title, scope, current):
    return nbf.v4.new_markdown_cell(
        f"## **Expiry-Day Liquidity Concentration in Indian Index Derivatives**\n\n"
        f"### **Notebook: {title}**\n\n"
        f"---\n\n"
        f"**Scope:** {scope}\n\n"
        f"---\n\n"
        f"### Pipeline sequence\n\n{PIPELINE_INDEX}\n\n"
        f"**Current location:** {current} <- *you are here*\n"
    )


def setup_cell():
    return nbf.v4.new_code_cell(
        "import sys\n"
        "from pathlib import Path\n\n"
        "project_dir = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
        "if str(project_dir) not in sys.path:\n"
        "    sys.path.append(str(project_dir))\n\n"
        "import pandas as pd\n"
        "import json\n"
        "from src import config\n\n"
        "pd.set_option('display.max_columns', 20)\n"
        "print('Project root:', project_dir)"
    )


def save(nb, filename):
    path = NB_DIR / filename
    nbf.write(nb, path)
    print(f"Wrote {path}")


def notebook_01():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "01: Data Collection",
            "Downloads Bank Nifty and Nifty 50 index OHLCV, constructs the settlement-weekday "
            "expiry calendar and trading holiday list, and (one-time, documented but not re-run "
            "here) pulls the full NSE futures-and-options Bhavcopy archive.",
            "**01_data_collection.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "### 1. Index OHLCV, expiry calendar, and holidays\n\n"
            "`src.data_loader.load_data_pipeline` downloads daily Bank Nifty OHLCV from Yahoo Finance, "
            "programmatically builds the monthly expiry calendar across the Thursday -> Wednesday -> "
            "Tuesday settlement-weekday reforms (rolling back for exchange holidays), and derives the "
            "holiday list from the trading calendar itself."
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "from src.data_loader import load_data_pipeline\n\n"
            "df_ohlcv, df_expiry, df_holidays = load_data_pipeline()\n"
            "print(f'OHLCV: {len(df_ohlcv)} rows, {df_ohlcv[\"Date\"].min()} to {df_ohlcv[\"Date\"].max()}')\n"
            "print(f'Expiry calendar: {len(df_expiry)} months')\n"
            "print(f'Holidays: {len(df_holidays)} days')\n"
            "df_expiry.tail(10)"
        ),
        nbf.v4.new_markdown_cell(
            "### 2. NSE futures-and-options Bhavcopy archive\n\n"
            "The primary analysis needs daily per-contract volume, traded value, and open interest for "
            "every Bank Nifty and Nifty 50 futures/options contract, which the index OHLCV above does "
            "not provide. This comes from NSE's own daily Bhavcopy archive, spanning a legacy CSV format "
            "(pre 2024-07-08) and the newer UDiFF format.\n\n"
            "Downloading the full 2020-2026 archive (~1,700 trading days) is a one-time, rate-limited "
            "step and is **not re-run in this notebook**. To (re)build it from scratch:\n\n"
            "```bash\n"
            "python -m scripts.download_fo_bhavcopy 2020-01-01 2026-10-18\n"
            "```\n\n"
            "The cell below just reports what is already on disk."
        ),
        nbf.v4.new_code_cell(
            "legacy_dir = config.RAW_DATA_DIR / 'fo_bhavcopy' / 'legacy'\n"
            "udiff_dir = config.RAW_DATA_DIR / 'fo_bhavcopy' / 'udiff'\n"
            "n_legacy = len(list(legacy_dir.glob('*.zip'))) if legacy_dir.exists() else 0\n"
            "n_udiff = len(list(udiff_dir.glob('*.zip'))) if udiff_dir.exists() else 0\n"
            "print(f'Legacy-format Bhavcopy files on disk: {n_legacy}')\n"
            "print(f'UDiFF-format Bhavcopy files on disk: {n_udiff}')\n"
            "print(f'Total: {n_legacy + n_udiff}')"
        ),
    ]
    save(nb, "01_data_collection.ipynb")


def notebook_02():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "02: Feature Engineering and F&O Construction",
            "Computes technical and range-based volatility features on index OHLCV, and parses the raw "
            "Bhavcopy archive into lot-size-invariant daily turnover and open-interest panels for Bank "
            "Nifty and Nifty 50.",
            "**02_feature_engineering_and_fo_construction.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "### 1. Technical and volatility features\n\n"
            "`src.features.add_all_features` adds RSI, MACD, Bollinger Bands, Average True Range, "
            "close-to-close rolling volatility, and the Parkinson and Garman-Klass range-based realized "
            "volatility estimators (used later in the interrupted-time-series check), plus the cyclical "
            "expiry-distance encoding."
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "features = pd.read_parquet(config.INTERIM_DATA_DIR / 'banknifty_features_true.parquet')\n"
            "print(f'{len(features)} rows, {features[\"Date\"].min()} to {features[\"Date\"].max()}')\n"
            "features[['Date', 'Close', 'Return', 'RSI', 'Parkinson_Vol_1d', 'GarmanKlass_Vol_1d',\n"
            "          'Days_To_Expiry', 'Expiry_Week']].tail(10)"
        ),
        nbf.v4.new_markdown_cell(
            "### 2. Lot-size-invariant F&O turnover and open interest\n\n"
            "`scripts.build_fo_volume_oi_dataset` and `scripts.build_nifty_volume_oi_dataset` parse the "
            "raw Bhavcopy archive (both formats) into one daily row per index, with total traded value "
            "(rupees, lot-size-invariant) and lot-size-adjusted notional open interest alongside the raw "
            "contract-count figures. This is a one-time parse of ~1,700 files per index; rebuild with:\n\n"
            "```bash\n"
            "python -m scripts.build_fo_volume_oi_dataset\n"
            "python -m scripts.build_nifty_volume_oi_dataset\n"
            "```\n\n"
            "The cell below loads the already-built panels."
        ),
        nbf.v4.new_code_cell(
            "bn_fo = pd.read_parquet(config.INTERIM_DATA_DIR / 'banknifty_fo_volume_oi.parquet')\n"
            "nf_fo = pd.read_parquet(config.INTERIM_DATA_DIR / 'nifty_fo_volume_oi.parquet')\n"
            "print(f'Bank Nifty F&O panel: {len(bn_fo)} days, {bn_fo[\"Date\"].min()} to {bn_fo[\"Date\"].max()}')\n"
            "print(f'Nifty 50 F&O panel: {len(nf_fo)} days')\n"
            "bn_fo[['Date', 'Total_Volume', 'Total_Value', 'Total_OpenInterest', 'Total_OpenInterest_Notional', 'LotSize']].tail(10)"
        ),
    ]
    save(nb, "02_feature_engineering_and_fo_construction.ipynb")


def notebook_03():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "03: Weekly-Options Discontinuation Identification",
            "Dates the Bank Nifty weekly-options discontinuation directly from the exchange's own "
            "contract listings, and confirms the coincident lot-size change that must be corrected for "
            "before any turnover/open-interest comparison across that date.",
            "**03_weekly_options_discontinuation_identification.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "### Why this matters\n\n"
            "A regulator rule limiting each exchange to one weekly index-derivatives contract forced NSE "
            "to discontinue Bank Nifty weekly options while Nifty 50 kept its own. Rather than relying on "
            "a secondary account of the exact date, this notebook counts the number of distinct Bank "
            "Nifty option expiry dates quoted in the Bhavcopy on each sampled day, which should drop "
            "sharply once weekly listings stop being renewed."
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "from src.regime_calendar import WEEKLY_OPTIONS_CUTOVER, TRANSITION_DATES\n\n"
            "print('Settlement-weekday transition dates:')\n"
            "for name, date in TRANSITION_DATES.items():\n"
            "    print(f'  {name}: {date.date()}')\n"
            "print()\n"
            "print(f'Weekly-options discontinuation cutover (identified from Bhavcopy contract counts): {WEEKLY_OPTIONS_CUTOVER.date()}')"
        ),
        nbf.v4.new_markdown_cell(
            "### Lot-size change coincident with the discontinuation\n\n"
            "Bank Nifty's exchange-set lot size also changed (15 to 30) within the same window, confirmed "
            "directly from the UDiFF archive's lot-size field. This is why the primary analysis uses "
            "traded value and notional open interest rather than raw contract counts."
        ),
        nbf.v4.new_code_cell(
            "bn_fo = pd.read_parquet(config.INTERIM_DATA_DIR / 'banknifty_fo_volume_oi.parquet')\n"
            "bn_fo['Date'] = pd.to_datetime(bn_fo['Date'])\n"
            "lot_by_month = bn_fo.set_index('Date')['LotSize'].resample('MS').median()\n"
            "lot_by_month.loc['2024-06-01':'2025-02-01']"
        ),
    ]
    save(nb, "03_weekly_options_discontinuation_identification.ipynb")


def notebook_04():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "04: Primary Difference-in-Differences Analysis",
            "Estimates the headline result: did Bank Nifty's expiry-day trading concentration rise more "
            "than Nifty 50's after the weekly-options removal?",
            "**04_primary_diff_in_diff_analysis.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "`scripts.diff_in_diff_banknifty_vs_nifty` pools daily Bank Nifty and Nifty 50 turnover (and, "
            "separately, open interest) and estimates\n\n"
            "```\n"
            "log(Value_it) = a + b1*Expiry_it + b2*MonthlyOnly_t + b3*BankNifty_i\n"
            "    + b4*(Expiry_it x MonthlyOnly_t) + b5*(Expiry_it x BankNifty_i)\n"
            "    + b6*(MonthlyOnly_t x BankNifty_i) + b7*(Expiry_it x MonthlyOnly_t x BankNifty_i)\n"
            "    + b8*Trend_t + weekday fixed effects + e_it\n"
            "```\n\n"
            "with Newey-West standard errors. The coefficient on the triple interaction (b7) is the "
            "causal estimate of interest."
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "from scripts.diff_in_diff_banknifty_vs_nifty import load_panel, triple_interaction_regression\n\n"
            "panel = load_panel()\n"
            "model_value = triple_interaction_regression(panel, 'Total_Value')\n"
            "model_oi = triple_interaction_regression(panel, 'Total_OpenInterest_Notional')\n"
            "print('=== log(Total_Value) ===')\n"
            "print(model_value.summary().tables[1])"
        ),
        nbf.v4.new_code_cell(
            "print('=== log(Total_OpenInterest_Notional) ===')\n"
            "print(model_oi.summary().tables[1])"
        ),
        nbf.v4.new_markdown_cell(
            "### Reading the result\n\n"
            "The `Expiry_x_Monthly_x_BankNifty` coefficient is the difference-in-differences estimate: "
            "how much more Bank Nifty's expiry-day activity rose, relative to Nifty 50, after the weekly "
            "contract was discontinued. A positive, significant coefficient on both turnover and open "
            "interest is the paper's primary finding."
        ),
    ]
    save(nb, "04_primary_diff_in_diff_analysis.ipynb")


def notebook_05():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "05: Robustness Checks",
            "Placebo cutover dates, leave-one-out exclusion of each treated expiry, and an event-study "
            "leads/lags specification, probing whether the primary result is a genuine discontinuity "
            "rather than an artifact of a longer-running trend or a handful of unusual observations.",
            "**05_robustness_checks.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "### Cached robustness results\n\n"
            "The full robustness battery (placebo dates, leave-one-out, and the event-study regression) "
            "is run by `scripts.diff_in_diff_banknifty_vs_nifty` and `scripts.event_study_leads_lags`. "
            "Rebuild with:\n\n"
            "```bash\n"
            "python -m scripts.diff_in_diff_banknifty_vs_nifty\n"
            "python -m scripts.event_study_leads_lags\n"
            "```\n\n"
            "This notebook loads the saved results."
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "with open(config.RESULTS_DIR / 'diff_in_diff_banknifty_vs_nifty.json') as f:\n"
            "    did = json.load(f)\n\n"
            "print('=== Placebo-date test (Total_Value) ===')\n"
            "for label, r in did['placebo_date_test_Total_Value'].items():\n"
            "    print(f\"{label}: coef={r['coef']:.4f}, p={r['p_value']:.4f}\")"
        ),
        nbf.v4.new_code_cell(
            "loo = did['leave_one_out_Total_Value']\n"
            "print('=== Leave-one-out (23 Bank Nifty Monthly-Only expiry days) ===')\n"
            "print(f\"Full-sample coefficient: {loo['full_sample_coef']:.4f}\")\n"
            "print(f\"Range across exclusions: [{loo['loo_coef_min']:.4f}, {loo['loo_coef_max']:.4f}]\")\n"
            "print(f\"Mean: {loo['loo_coef_mean']:.4f}, SD: {loo['loo_coef_std']:.4f}\")"
        ),
        nbf.v4.new_code_cell(
            "with open(config.RESULTS_DIR / 'event_study_leads_lags.json') as f:\n"
            "    event_study = json.load(f)\n\n"
            "pd.DataFrame(event_study['Total_Value']).sort_values('period_half_years_from_event')"
        ),
    ]
    save(nb, "05_robustness_checks.ipynb")


def notebook_06():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "06: Expiry Volume Event Study",
            "Descriptive expiry-day trading-activity patterns, stratified by settlement-weekday regime "
            "and weekly-options liquidity regime, and the pooled regression version of the same test.",
            "**06_expiry_volume_event_study.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "`scripts.expiry_volume_oi_event_study` compares expiry-day turnover/open interest against "
            "same-weekday non-expiry days, within each settlement-regime x liquidity-regime stratum. "
            "Rebuild with:\n\n"
            "```bash\n"
            "python -m scripts.expiry_volume_oi_event_study\n"
            "```"
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "with open(config.RESULTS_DIR / 'expiry_volume_oi_event_study.json') as f:\n"
            "    ev = json.load(f)\n\n"
            "pd.DataFrame(ev['expiry_vs_nonexpiry_by_stratum_Total_Volume'])"
        ),
        nbf.v4.new_code_cell(
            "pd.DataFrame(ev['expiry_vs_nonexpiry_by_stratum_Total_OpenInterest'])"
        ),
    ]
    save(nb, "06_expiry_volume_event_study.ipynb")


def notebook_07():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "07: Walk-Forward Predictability (Secondary, Null Result)",
            "Tests whether the settlement-weekday reforms created exploitable next-day return "
            "predictability, using a leakage-free five-fold expanding-window protocol. Reported "
            "honestly as a null result.",
            "**07_walk_forward_predictability.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "### Why this is in the paper despite being null\n\n"
            "This is the question an expiration-day calendar-effects study would typically ask first. The "
            "full five-fold refit (`scripts.walk_forward_backtest`) refits both the regime-detection model "
            "and the forecasting model within each fold, so it takes a few minutes to run end-to-end; "
            "rebuild with:\n\n"
            "```bash\n"
            "python -m scripts.walk_forward_backtest\n"
            "```\n\n"
            "This notebook loads the saved results rather than re-running the fit."
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "with open(config.RESULTS_DIR / 'walk_forward_results.json') as f:\n"
            "    wf = json.load(f)\n\n"
            "conditions = ['Baseline (Technical Only)', 'Baseline + Expiry', 'Baseline + Regime', 'Proposed (Combined)']\n"
            "rows = []\n"
            "for cnd in conditions:\n"
            "    ci = wf['pooled_significance'][f'DirAcc_CI_{cnd}']\n"
            "    rows.append({'Condition': cnd, 'Accuracy': ci['accuracy_mean'], 'CI_low': ci['ci_2.5'], 'CI_high': ci['ci_97.5']})\n"
            "pd.DataFrame(rows)"
        ),
        nbf.v4.new_code_cell(
            "dm = wf['pooled_significance']['DM_test_pooled']\n"
            "sharpe = wf['pooled_significance']['Sharpe_diff_bootstrap']\n"
            "print(f\"Pooled Diebold-Mariano p-value (baseline vs. combined): {dm['P_Value_Two_Sided']:.4f}\")\n"
            "print(f\"Pooled Sharpe-ratio difference (combined minus baseline): {sharpe['diff_mean']:.4f} \"\n"
            "      f\"[{sharpe['ci_2.5']:.4f}, {sharpe['ci_97.5']:.4f}]\")"
        ),
        nbf.v4.new_markdown_cell(
            "Every condition's confidence interval straddles 50% chance accuracy, and the pooled "
            "Diebold-Mariano test does not reject equal predictive accuracy. This null result is reported "
            "alongside the primary liquidity-concentration finding rather than omitted."
        ),
    ]
    save(nb, "07_walk_forward_predictability.ipynb")


def notebook_08():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "08: Interrupted Time Series (Secondary, Null Result)",
            "Tests whether the settlement-weekday reforms shifted expiry-week returns or realized "
            "volatility directly, independent of the predictive-modeling exercise in notebook 07. Also "
            "reported honestly as a null result.",
            "**08_interrupted_time_series.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "`scripts.regime_shift_event_study` regresses daily return (and two realized-volatility "
            "measures, including a Parkinson range-based estimator) on expiry-week status interacted "
            "with settlement regime. Rebuild with:\n\n"
            "```bash\n"
            "python -m scripts.regime_shift_event_study\n"
            "```"
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "with open(config.RESULTS_DIR / 'regime_shift_event_study.json') as f:\n"
            "    its = json.load(f)\n\n"
            "for model_key, label in [('its_return_model', 'Return'), ('its_parkinson_vol_model', 'Parkinson volatility')]:\n"
            "    m = its[model_key]\n"
            "    print(f'=== {label} ===')\n"
            "    for term in ['EW_x_Wed', 'EW_x_Tue']:\n"
            "        print(f\"  {term}: coef={m['params'][term]:.4f}, p={m['p_values'][term]:.4f}\")"
        ),
        nbf.v4.new_markdown_cell(
            "None of the expiry-week x settlement-regime interaction terms are statistically significant, "
            "across both the return and the volatility specifications. Combined with notebook 07, neither "
            "secondary analysis finds evidence that the settlement-weekday reforms changed return or "
            "volatility behavior, consistent with the primary result operating through trading "
            "concentration rather than price predictability."
        ),
    ]
    save(nb, "08_interrupted_time_series.ipynb")


def notebook_09():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        header_cell(
            "09: Figures for the Paper",
            "Regenerates the three figures used in the manuscript directly from the saved results JSON "
            "files, and displays them inline.",
            "**09_figures_for_paper.ipynb**",
        ),
        nbf.v4.new_markdown_cell(
            "`scripts.make_pbfj_figures` builds all three figures at 300 dpi. Rebuild with:\n\n"
            "```bash\n"
            "python -m scripts.make_pbfj_figures\n"
            "```"
        ),
        setup_cell(),
        nbf.v4.new_code_cell(
            "from scripts.make_pbfj_figures import (\n"
            "    fig_event_study_leads_lags, fig_expiry_volume_profile, fig_walk_forward_directional_accuracy,\n"
            ")\n\n"
            "fig_event_study_leads_lags()\n"
            "fig_expiry_volume_profile()\n"
            "fig_walk_forward_directional_accuracy()"
        ),
        nbf.v4.new_code_cell(
            "from IPython.display import Image, display\n\n"
            "for fname in ['expiry_volume_profile.png', 'event_study_leads_lags.png', 'walk_forward_directional_accuracy.png']:\n"
            "    display(Image(filename=str(config.FIGURES_DIR / fname)))"
        ),
    ]
    save(nb, "09_figures_for_paper.ipynb")



# ---------------------------------------------------------------------------------------------
# Corrected-pipeline notebooks (override the older wrong-calendar versions above)
# ---------------------------------------------------------------------------------------------
def _nb(title, scope, current, cells, fname):
    nb = nbf.v4.new_notebook()
    nb.cells = [header_cell(title, scope, current), setup_cell()] + cells
    save(nb, fname)


def _md(t):
    return nbf.v4.new_markdown_cell(t)


def _code(*lines):
    return nbf.v4.new_code_cell("\n".join(lines))


def notebook_03():
    _nb("03: True Expiry Dates and Calendar Audit",
        "Takes expiry dates per index from the Bhavcopy expiry field and audits the old rule-based calendar.",
        "**03_weekly_options_discontinuation_identification.ipynb**",
        [_md("Rebuild with `python -m scripts.build_index_expiry_panel` (~15 min). The old calendar in "
             "`data/raw/nse_expiry_calendar.csv` mis-flags many expiries (audit below) and must not be used."),
         _code("ex = pd.read_parquet(config.INTERIM_DATA_DIR / 'index_expiry_dates.parquet')",
               "bn = ex[(ex.Symbol == 'BANKNIFTY') & ex.IsMonthly].copy()",
               "bn['Weekday'] = bn.ExpiryDate.dt.day_name()",
               "bn.tail(24)"),
         _code("json.load(open(config.RESULTS_DIR / 'corrected_robustness.json'))['calendar_audit']"),
         _code("p = pd.read_parquet(config.INTERIM_DATA_DIR / 'index_expiry_panel.parquet')",
               "p[p.Symbol == 'BANKNIFTY'].set_index('Date')['NExpiriesListed'].loc['2024-10-10':'2024-11-20']")],
        "03_weekly_options_discontinuation_identification.ipynb")


def _results_nb(fname, title, scope, *code_lines, extra=None):
    cells = [_md("Results are produced by the scripts named in the scope line; this notebook loads them."),
             _code(*code_lines)]
    if extra:
        cells += extra
    _nb(title, scope, f"**{fname}**", cells, fname)


def notebook_04():
    _nb("04: Corrected Difference-in-Differences (NSE and BSE)",
        "True-expiry symbol-month DiD. Within-exchange: Bank Nifty vs Nifty (NSE) and Bankex vs Sensex (BSE). "
        "Pooled: six indices, symbol and month fixed effects, exact randomization inference over the 15 treatment "
        "assignments. Reproduce: `python -m scripts.did_monthly_true_expiry`, `python -m scripts.cross_exchange_did`.",
        "**04_primary_diff_in_diff_analysis.ipynb**",
        [_md("### 1. NSE only (Nifty control; Nifty is contaminated by substitution)\n"
             "Outcomes are log points: `lt` total turnover, `le` expiry-day turnover, `ls` expiry-day share."),
         _code("r = json.load(open(config.RESULTS_DIR / 'did_monthly_true_expiry.json'))",
               "pd.DataFrame({k: v for k, v in r.items() if not k.startswith('eventstudy')}).T"),
         _md("### 2. Cross-exchange replication and pooled design\n"
             "BSE retired Bankex weeklies but kept Sensex weeklies. The pooled estimate uses only 6 units, so "
             "inference is by exact randomization over treatment assignments (minimum attainable p = 1/15)."),
         _code("x = json.load(open(config.RESULTS_DIR / 'cross_exchange_did.json'))",
               "within = {k: {o: round(v['coef'], 2) for o, v in x[k].items()} for k in x if ': ' in k}",
               "print(pd.DataFrame(within).T)",
               "print(pd.DataFrame(x['pooled_twfe']).T)")],
        "04_primary_diff_in_diff_analysis.ipynb")


def notebook_05():
    _nb("05: Robustness, Substitution and Market Quality",
        "In-time placebo, Bank-Nifty-only before/after, window sensitivity; substitution accounting with a sensitivity "
        "range for organic growth; participant mix; futures market-quality spillovers. Reproduce: "
        "`python -m scripts.substitution_placebo_audit`, `python -m scripts.cross_exchange_did`, "
        "`python -m scripts.market_quality_did`.",
        "**05_robustness_checks.ipynb**",
        [_md("### 1. Placebo, BN-only and window sensitivity (NSE)"),
         _code("r = json.load(open(config.RESULTS_DIR / 'corrected_robustness.json'))",
               "keys = ['in_time_placebo', 'bn_only_before_after', 'window_sensitivity']",
               "print(json.dumps({k: r[k] for k in keys}, indent=1))"),
         _md("### 2. Substitution (six indices)\n"
             "The raw share is ~99%, but both controls were growing fast before the reform, so the share depends on the "
             "assumed organic growth. Treat it as a range, not a point estimate."),
         _code("x = json.load(open(config.RESULTS_DIR / 'cross_exchange_did.json'))",
               "print(json.dumps(x['substitution'], indent=1))",
               "print(json.dumps(x['participants'], indent=1))"),
         _md("### 3. Market quality (near-month index futures; spillover outcomes, not option spreads)"),
         _code("q = json.load(open(config.RESULTS_DIR / 'market_quality_did.json'))",
               "within = {k: {o: (round(v['coef'], 4), round(v['p'], 3)) for o, v in q[k].items()} for k in q if ': ' in k}",
               "print(pd.DataFrame(within).T)",
               "print(pd.DataFrame(q['pooled_twfe']).T)")],
        "05_robustness_checks.ipynb")


def notebook_06():
    _nb("06: Expiry-Day Concentration (six indices)",
        "Monthly expiry-day turnover and share for NSE and BSE indices, and the turnover profile around true expiries.",
        "**06_expiry_volume_event_study.ipynb**",
        [_code("m = pd.read_parquet(config.INTERIM_DATA_DIR / 'monthly_expiry_panel_all.parquet')",
               "m = m[(m.exp_day > 0) & (m.ym >= pd.Period('2023-06')) & (m.ym != pd.Period('2024-11'))].copy()",
               "m['period'] = (m.ym >= pd.Period('2024-12')).map({False: 'pre', True: 'post'})",
               "m.groupby(['Symbol', 'period'])[['tot', 'exp_day', 'share', 'nexp']].mean()"),
         _code("from IPython.display import Image, display",
               "for f in ['fig5_six_index_turnover.png', 'fig4_expiry_profile_true.png']:",
               "    display(Image(filename=str(config.FIGURES_DIR / f)))")],
        "06_expiry_volume_event_study.ipynb")


def notebook_07():
    _results_nb("07_walk_forward_predictability.ipynb", "07: Walk-Forward Predictability (True Calendar)",
                "Five-fold expanding-window evaluation (`python -m scripts.build_features_true_calendar`, then "
                "`python -m scripts.walk_forward_backtest`).",
                "w = json.load(open(config.RESULTS_DIR / 'walk_forward_results_true_calendar.json'))['pooled_significance']",
                "keep = ('DM_test_pooled', 'Holm_Bonferroni_adjusted', 'Sharpe_diff_bootstrap')",
                "{k: w[k] for k in w if k.startswith('DirAcc_CI') or k in keep}")


def notebook_08():
    _results_nb("08_interrupted_time_series.ipynb", "08: Interrupted Time Series and Clean Weekday Contrasts",
                "Full-sample ITS on the four true regimes plus within-structure weekday contrasts "
                "(`python -m scripts.regime_shift_event_study`, `python -m scripts.its_clean_contrasts`).",
                "r = json.load(open(config.RESULTS_DIR / 'regime_shift_event_study_true_calendar.json'))",
                "its = {k: {p: round(v['p_values'][p], 3) for p in v['params'] if p.startswith('EW_x')}",
                "       for k, v in r.items() if k.startswith('its_')}",
                "print(pd.DataFrame(its).T)",
                "print(json.dumps(json.load(open(config.RESULTS_DIR / 'its_clean_contrasts.json')), indent=1))")


def notebook_09():
    _results_nb("09_figures_for_paper.ipynb", "09: Corrected Figures",
                "Regenerate with `python -m scripts.make_corrected_figures`.",
                "from IPython.display import Image, display",
                "figs = ['fig1_turnover_and_share', 'fig2_event_study', 'fig3_walk_forward_true_calendar', 'fig4_expiry_profile_true', 'fig5_six_index_turnover', 'fig6_timing_and_stock_placebo']",
                "for f in figs:",
                "    display(Image(filename=str(config.FIGURES_DIR / (f + '.png'))))")



def notebook_10():
    _nb("10: Option Microstructure, Placebo and Dose-Response",
        "Contract-level index-option outcomes (days-to-expiry mix, far-OTM share, exploratory ATM high-low measures), "
        "the never-weekly stock-F&O placebo and the daily dose-response around the Nov-2024 transition. Reproduce: "
        "`python -m scripts.build_option_contract_panel` (~5 min), `python -m scripts.option_microstructure_did`.",
        "**10_option_microstructure_and_placebo.ipynb**",
        [_md("### 1. Placebo and dose-response\n"
             "Stock F&O never had weeklies: if the collapse were a market-wide shock (margins, lot sizes, taxes) it would "
             "show there too. The dose-response regresses the daily Bank Nifty-vs-Nifty log turnover gap on the number of "
             "Bank Nifty option expiries listed while the weeklies rolled off."),
         _code("r = json.load(open(config.RESULTS_DIR / 'option_microstructure_did.json'))",
               "print(json.dumps({k: r[k] for k in ['stock_placebo', 'dose_response']}, indent=1))"),
         _md("### 2. Contract-level outcomes\n"
             "`dte01_share` and `dte07_share` are turnover shares in contracts within 1 / 7 days of expiry; `otm5_share` is "
             "the share in options more than 5% out of the money. `atm_cs` and `atm_hl` are exploratory: Corwin-Schultz "
             "spreads of 14-22% for options mostly reflect volatility and price level, so do NOT read them as market quality."),
         _code("within = {k: {o: (round(v['coef'], 3), round(v['p'], 3)) for o, v in r[k].items()} for k in r if ': ' in k}",
               "print(pd.DataFrame(within).T)",
               "print(pd.DataFrame(r['pooled_twfe']).T)",
               "pd.concat({s: pd.DataFrame(v).T for s, v in r['descriptives'].items()}).round(3)"),
         _code("from IPython.display import Image, display",
               "display(Image(filename=str(config.FIGURES_DIR / 'fig6_timing_and_stock_placebo.png')))")],
        "10_option_microstructure_and_placebo.ipynb")



if __name__ == "__main__":
    NB_DIR.mkdir(parents=True, exist_ok=True)
    notebook_01()
    notebook_02()
    notebook_03()
    notebook_04()
    notebook_05()
    notebook_06()
    notebook_07()
    notebook_08()
    notebook_09()
    notebook_10()
    print("\nAll 10 notebooks written.")
