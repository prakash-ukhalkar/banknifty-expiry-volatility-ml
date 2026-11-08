"""
Walk-forward (expanding-window) robustness check for the Bank Nifty expiry-regime study.

Rationale: the paper's headline Sharpe ratio (2.10) and directional accuracy (54.42%)
come from a single fixed test window (2025-11-18 to 2026-06-24, 147 trading days).
This script re-runs the full pipeline (HMM regime fit -> feature set -> OLS -> backtest)
across multiple expanding-window folds so the result can be reported as a distribution
rather than a single point estimate, and adds significance tests that were missing
from the original evaluation (bootstrap CI on Sharpe difference, bootstrap CI on
directional accuracy vs. 50%).

No look-ahead: for every fold, the HMM is refit on that fold's training portion only,
then regime probabilities for the held-out test portion are produced with a *separate*
predict_proba call on the test portion alone (matching notebooks/04's methodology of
never fitting or scoring train+test jointly).
"""
import json
import numpy as np
import pandas as pd
from scipy.stats import binomtest

from src import config
from src.models import build_xgb_regressor, train_model
from src.evaluation import calculate_metrics, diebold_mariano_test, backtest_trading_strategy
from src.regime_detection import VolatilityRegimeDetector
from src.regime_calendar import tag_expiry_regime


def holm_bonferroni(pvalues):
    """Holm-Bonferroni step-down correction. Returns dict name -> adjusted p-value."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted = {}
    running_max = 0.0
    for i, (name, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        running_max = max(running_max, adj)
        adjusted[name] = running_max
    return adjusted

RANDOM_STATE = config.RANDOM_SEED
N_FOLDS = 5
MIN_TRAIN_FRAC = 0.45  # first fold trains on ~45% of data, matching original ~60% train-only order of magnitude
N_BOOTSTRAP = 5000

BASELINE_FEATS = ['RSI', 'MACD', 'MACD_Signal', 'MACD_Hist', 'BB_Mid', 'BB_Upper',
                   'BB_Lower', 'BB_PctB', 'BB_Width', 'ATR', 'Rolling_Vol', 'Return']
EXPIRY_FEATS = ['Days_To_Expiry', 'Expiry_Week', 'Expiry_Dist_Sin', 'Expiry_Dist_Cos']
REGIME_FEATS = ['Regime_Prob_Calm', 'Regime_Prob_Stressed']

CONDITIONS = {
    "Baseline (Technical Only)": BASELINE_FEATS,
    "Baseline + Expiry": BASELINE_FEATS + EXPIRY_FEATS,
    "Baseline + Regime": BASELINE_FEATS + REGIME_FEATS,
    "Proposed (Combined)": BASELINE_FEATS + EXPIRY_FEATS + REGIME_FEATS,
}


def load_base_dataset():
    df = pd.read_parquet(config.INTERIM_DATA_DIR / "banknifty_features_true.parquet")
    df['Date'] = pd.to_datetime(df['Date'])
    df['Target'] = df['Return'].shift(-1)
    df = df.dropna().reset_index(drop=True)
    return df


def make_fold_indices(n, n_folds, min_train_frac):
    """Expanding window: train grows each fold, test is a fixed-size forward slice."""
    first_train_end = int(n * min_train_frac)
    remaining = n - first_train_end
    test_size = remaining // n_folds
    folds = []
    train_end = first_train_end
    for i in range(n_folds):
        test_start = train_end
        test_end = test_start + test_size if i < n_folds - 1 else n
        if test_end <= test_start:
            break
        folds.append((0, train_end, test_start, test_end))
        train_end = test_end
    return folds


def add_regime_features(train_df, test_df):
    detector = VolatilityRegimeDetector(n_components=2, random_state=RANDOM_STATE)
    detector.fit(train_df)
    train_probs = detector.predict_proba(train_df)
    test_probs = detector.predict_proba(test_df)
    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df['Regime_Prob_Calm'] = train_probs[:, 0]
    train_df['Regime_Prob_Stressed'] = train_probs[:, 1]
    test_df['Regime_Prob_Calm'] = test_probs[:, 0]
    test_df['Regime_Prob_Stressed'] = test_probs[:, 1]
    return train_df, test_df


def bootstrap_sharpe_diff_ci(returns_a, returns_b, n_boot=N_BOOTSTRAP, seed=RANDOM_STATE):
    """Block-free paired bootstrap on daily net returns of two strategies (a - b), annualized Sharpe diff."""
    rng = np.random.default_rng(seed)
    a = np.asarray(returns_a)
    b = np.asarray(returns_b)
    n = len(a)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        sa, sb = a[idx], b[idx]
        sharpe_a = (sa.mean() / sa.std()) * np.sqrt(252) if sa.std() > 1e-9 else 0.0
        sharpe_b = (sb.mean() / sb.std()) * np.sqrt(252) if sb.std() > 1e-9 else 0.0
        diffs[i] = sharpe_a - sharpe_b
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    p_le_zero = float(np.mean(diffs <= 0))
    return {"diff_mean": float(diffs.mean()), "ci_2.5": float(lo), "ci_97.5": float(hi), "p_diff_le_0": p_le_zero}


def bootstrap_directional_accuracy_ci(y_true, y_pred, n_boot=N_BOOTSTRAP, seed=RANDOM_STATE):
    rng = np.random.default_rng(seed)
    correct = (np.sign(y_true) == np.sign(y_pred)).astype(float)
    n = len(correct)
    boot_means = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        boot_means[i] = correct[idx].mean()
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    p_le_half = float(np.mean(boot_means <= 0.5))
    return {"accuracy_mean": float(correct.mean()), "ci_2.5": float(lo), "ci_97.5": float(hi), "p_le_50pct": p_le_half}


def run():
    df = load_base_dataset()
    folds = make_fold_indices(len(df), N_FOLDS, MIN_TRAIN_FRAC)
    print(f"Dataset: {len(df)} rows, {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(f"Running {len(folds)} expanding-window folds\n")

    fold_records = []
    all_returns_by_condition = {name: [] for name in CONDITIONS}
    all_ytrue_by_condition = {name: [] for name in CONDITIONS}
    all_ypred_by_condition = {name: [] for name in CONDITIONS}
    # Per-regime pools, so results can be reported without averaging across the
    # Thursday/Wednesday/Tuesday structural break (reviewers' core design critique).
    regime_ytrue_by_condition = {name: {} for name in CONDITIONS}
    regime_ypred_by_condition = {name: {} for name in CONDITIONS}

    for fold_i, (tr_start, tr_end, te_start, te_end) in enumerate(folds, start=1):
        train_raw = df.iloc[tr_start:tr_end]
        test_raw = df.iloc[te_start:te_end]
        train_feat, test_feat = add_regime_features(train_raw, test_raw)
        test_regime = tag_expiry_regime(test_raw['Date']).values

        date_range = f"{test_raw['Date'].min().date()} -> {test_raw['Date'].max().date()}"
        regimes_in_fold = sorted(set(test_regime))
        print(f"Fold {fold_i}: train={len(train_feat)} test={len(test_feat)}  test window {date_range}  regimes={regimes_in_fold}")

        for name, feats in CONDITIONS.items():
            X_train, y_train = train_feat[feats], train_feat['Target']
            X_test, y_test = test_feat[feats], test_feat['Target']

            model = build_xgb_regressor()
            model = train_model(model, X_train, y_train)
            preds = model.predict(X_test)

            metrics = calculate_metrics(y_test, preds)
            backtest = backtest_trading_strategy(y_test, preds)

            fold_records.append({
                "Fold": fold_i,
                "Test_Start": str(test_raw['Date'].min().date()),
                "Test_End": str(test_raw['Date'].max().date()),
                "Regimes": ",".join(regimes_in_fold),
                "Condition": name,
                **metrics,
                "Sharpe_Ratio": backtest["Sharpe_Ratio"],
                "Total_Return": backtest["Total_Return"],
                "Max_Drawdown": backtest["Max_Drawdown"],
            })

            all_returns_by_condition[name].extend(backtest["Net_Returns"])
            all_ytrue_by_condition[name].extend(np.asarray(y_test).tolist())
            all_ypred_by_condition[name].extend(np.asarray(preds).tolist())

            y_test_arr = np.asarray(y_test)
            preds_arr = np.asarray(preds)
            for regime in regimes_in_fold:
                mask = test_regime == regime
                regime_ytrue_by_condition[name].setdefault(regime, []).extend(y_test_arr[mask].tolist())
                regime_ypred_by_condition[name].setdefault(regime, []).extend(preds_arr[mask].tolist())

    df_folds = pd.DataFrame(fold_records)

    print("\n=== Per-fold results ===")
    print(df_folds.to_string(index=False))

    print("\n=== Across-fold summary (mean +/- std) ===")
    summary = df_folds.groupby("Condition").agg(
        RMSE_mean=("RMSE", "mean"), RMSE_std=("RMSE", "std"),
        DirAcc_mean=("Directional_Accuracy", "mean"), DirAcc_std=("Directional_Accuracy", "std"),
        Sharpe_mean=("Sharpe_Ratio", "mean"), Sharpe_std=("Sharpe_Ratio", "std"),
    )
    print(summary)

    # Pooled (all folds' out-of-sample days concatenated) significance tests
    print("\n=== Pooled bootstrap significance tests (all fold test-days concatenated) ===")
    pooled_results = {}
    baseline_name = "Baseline (Technical Only)"
    proposed_name = "Proposed (Combined)"

    dm = diebold_mariano_test(
        all_ytrue_by_condition[proposed_name],
        all_ypred_by_condition[baseline_name],
        all_ypred_by_condition[proposed_name],
    )
    print("Pooled DM test (Baseline vs Proposed, MSE):", dm)
    pooled_results["DM_test_pooled"] = dm

    sharpe_ci = bootstrap_sharpe_diff_ci(
        all_returns_by_condition[proposed_name], all_returns_by_condition[baseline_name]
    )
    print("Pooled bootstrap Sharpe diff (Proposed - Baseline):", sharpe_ci)
    pooled_results["Sharpe_diff_bootstrap"] = sharpe_ci

    binomial_pvalues = {}
    for name in CONDITIONS:
        acc_ci = bootstrap_directional_accuracy_ci(
            all_ytrue_by_condition[name], all_ypred_by_condition[name]
        )
        print(f"Pooled directional accuracy CI [{name}]:", acc_ci)
        pooled_results[f"DirAcc_CI_{name}"] = acc_ci

        correct = (np.sign(all_ytrue_by_condition[name]) == np.sign(all_ypred_by_condition[name]))
        n_correct, n_total = int(np.sum(correct)), len(correct)
        bt = binomtest(n_correct, n_total, p=0.5, alternative="greater")
        binomial_pvalues[name] = float(bt.pvalue)
        pooled_results[f"Binomial_vs_50pct_{name}"] = {
            "n_correct": n_correct, "n_total": n_total, "p_value": float(bt.pvalue)
        }
        print(f"Binomial test vs 50% [{name}]: {n_correct}/{n_total} correct, p={bt.pvalue:.4f}")

    print("\n=== Holm-Bonferroni correction across the 4 conditions' binomial tests ===")
    adjusted = holm_bonferroni(binomial_pvalues)
    for name, p_adj in adjusted.items():
        print(f"{name}: raw p={binomial_pvalues[name]:.4f} -> Holm-adjusted p={p_adj:.4f}")
    pooled_results["Holm_Bonferroni_adjusted"] = adjusted

    # Per-regime directional accuracy (Thursday/Wednesday/Tuesday eras), so no number
    # is pooled across the structural settlement-day break.
    print("\n=== Per-regime directional accuracy (pooled across folds within each regime) ===")
    per_regime_results = {}
    for name in CONDITIONS:
        per_regime_results[name] = {}
        for regime, yt in regime_ytrue_by_condition[name].items():
            yp = regime_ypred_by_condition[name][regime]
            acc_ci = bootstrap_directional_accuracy_ci(yt, yp)
            per_regime_results[name][regime] = acc_ci
            print(f"[{name}] {regime} (n={len(yt)}): acc={acc_ci['accuracy_mean']:.4f} "
                  f"CI=[{acc_ci['ci_2.5']:.4f},{acc_ci['ci_97.5']:.4f}] p(<=50%)={acc_ci['p_le_50pct']:.4f}")
    pooled_results["per_regime_directional_accuracy"] = per_regime_results

    out = {
        "per_fold": df_folds.to_dict(orient="records"),
        "summary": summary.reset_index().to_dict(orient="records"),
        "pooled_significance": pooled_results,
    }
    out_path = config.RESULTS_DIR / "walk_forward_results_true_calendar.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved walk-forward results to {out_path}")


if __name__ == "__main__":
    run()
