"""
Runs the linear-vs-tree comparison the manuscript claims to have made but the
pipeline never actually performed (build_xgb_regressor previously returned a
LinearRegression wrapper regardless of the function name). This trains a real,
regularized XGBRegressor alongside the OLS model on the original fixed
train/val/test split (same split used in the submitted paper) across all four
feature conditions, so Table 2 / the "OLS outperforms XGBoost" claim can be
either substantiated or corrected with real numbers.
"""
import json
import pandas as pd

from src import config
from src.models import build_linear_regressor, build_xgb_regressor, train_model
from src.evaluation import calculate_metrics, diebold_mariano_test

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


def run():
    train = pd.read_parquet(config.PROCESSED_DATA_DIR / "train.parquet")
    val = pd.read_parquet(config.PROCESSED_DATA_DIR / "val.parquet")
    test = pd.read_parquet(config.PROCESSED_DATA_DIR / "test.parquet")

    results = []
    preds_by_model = {}

    for name, feats in CONDITIONS.items():
        X_train, y_train = train[feats], train['Target']
        X_val, y_val = val[feats], val['Target']
        X_test, y_test = test[feats], test['Target']

        ols = build_linear_regressor()
        ols = train_model(ols, X_train, y_train)
        ols_preds = ols.predict(X_test)
        ols_metrics = calculate_metrics(y_test, ols_preds)
        ols_metrics.update({"Model_Type": "OLS", "Condition": name})
        results.append(ols_metrics)
        preds_by_model[f"OLS::{name}"] = ols_preds

        xgb_model = build_xgb_regressor()
        xgb_model = train_model(xgb_model, X_train, y_train, X_val, y_val)
        xgb_preds = xgb_model.predict(X_test)
        xgb_metrics = calculate_metrics(y_test, xgb_preds)
        xgb_metrics.update({"Model_Type": "XGBoost", "Condition": name})
        results.append(xgb_metrics)
        preds_by_model[f"XGB::{name}"] = xgb_preds

    df = pd.DataFrame(results)[["Model_Type", "Condition", "RMSE", "MAE", "Directional_Accuracy"]]
    print(df.to_string(index=False))

    print("\n=== DM test: OLS vs XGBoost, per condition (H1: XGBoost more accurate) ===")
    dm_results = {}
    for name in CONDITIONS:
        y_test = test['Target']
        dm = diebold_mariano_test(y_test, preds_by_model[f"OLS::{name}"], preds_by_model[f"XGB::{name}"])
        print(name, dm)
        dm_results[name] = dm

    naive_rmse = ((test['Target'] - test['Target'].mean()) ** 2).mean() ** 0.5
    print(f"\nNaive (historical mean) RMSE on this test set: {naive_rmse:.6f}")

    out_path = config.RESULTS_DIR / "ols_vs_xgb_comparison.json"
    with open(out_path, "w") as f:
        json.dump({
            "table": df.to_dict(orient="records"),
            "dm_ols_vs_xgb": dm_results,
            "naive_rmse": naive_rmse,
        }, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    run()
