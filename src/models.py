"""
Model definition and training module for Baseline and Proposed architectures.
"""
import numpy as np
import xgboost as xgb
from sklearn.linear_model import LinearRegression
from . import config

class LinearRegressionWrapper(LinearRegression):
    """
    A wrapper around sklearn's LinearRegression that mimics the XGBoost interface
    (specifically providing feature_importances_) for notebook compatibility.
    """
    def __init__(self, *, fit_intercept=True, copy_X=True, n_jobs=None, positive=False):
        super().__init__(
            fit_intercept=fit_intercept,
            copy_X=copy_X,
            n_jobs=n_jobs,
            positive=positive
        )
        
    @property
    def feature_importances_(self):
        # Calculate feature importances as absolute coefficients normalized to sum to 1.0
        coef_abs = np.abs(self.coef_)
        total = np.sum(coef_abs)
        if total > 1e-9:
            return coef_abs / total
        else:
            return np.ones_like(coef_abs) / len(coef_abs)

def build_linear_regressor():
    """
    Builds the OLS linear regression model used as the paper's proposed architecture.
    """
    return LinearRegressionWrapper()

def build_xgb_regressor(params=None):
    """
    Builds a regularized XGBoost regressor, used for the linear-vs-tree comparison.

    Note: an earlier version used reg_alpha=1.0/reg_lambda=5.0 with max_depth=2,
    which made every candidate split's gain negative under XGBoost's default
    objective -- the booster never split past a single root leaf (tree dump:
    "0:leaf=-0") and early stopping locked in at iteration 0. That produced a
    constant-~0 predictor identical across every feature condition, which looked
    like (but was not) a fair XGBoost-vs-OLS comparison. The settings below were
    verified (via scripts/compare_ols_xgb.py) to let the booster actually split on
    the input features -- predictions now differ across feature conditions.
    """
    default_params = dict(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.05,
        reg_alpha=0.1,
        reg_lambda=1.0,
        min_child_weight=1,
        gamma=0,
        subsample=0.8,
        colsample_bytree=0.8,
        early_stopping_rounds=20,
        random_state=config.RANDOM_SEED,
    )
    if params:
        default_params.update(params)
    return xgb.XGBRegressor(**default_params)

def train_model(model, X_train, y_train, X_val=None, y_val=None, early_stopping_rounds=15):
    """
    Trains the provided model. If it is a Linear Regression wrapper, it fits directly
    without validation data or early stopping.
    """
    if isinstance(model, LinearRegressionWrapper):
        model.fit(X_train, y_train)
    else:
        # XGBoost logic
        if X_val is not None and y_val is not None:
            if hasattr(model, 'early_stopping_rounds') and model.early_stopping_rounds is None:
                model.set_params(early_stopping_rounds=early_stopping_rounds)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        else:
            if hasattr(model, 'early_stopping_rounds') and model.early_stopping_rounds is not None:
                model.set_params(early_stopping_rounds=None)
            model.fit(X_train, y_train)
    return model
