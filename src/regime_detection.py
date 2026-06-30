"""
Regime detection using Hidden Markov Models (HMM) on returns and realized volatility.
"""
from hmmlearn import hmm
import pandas as pd
import numpy as np

class VolatilityRegimeDetector:
    """
    Fits HMM on historical return/volatility to label states (State 0 = Calm, State 1 = Stressed).
    Enforces consistent state ordering by sorting states by variance.
    """
    def __init__(self, n_components=2, random_state=42):
        self.n_components = n_components
        self.random_state = random_state
        self.model = None

    def fit(self, X):
        """
        Fits unsupervised HMM on the log-volatility feature.
        """
        # Convert to numpy array if DataFrame
        if isinstance(X, pd.DataFrame):
            if 'Log_Rolling_Vol' in X.columns:
                X_arr = X[['Log_Rolling_Vol']].dropna().values
            else:
                X_arr = np.log(X[['Rolling_Vol']]).dropna().values
        else:
            X_arr = X
            
        # Initialize Gaussian HMM
        self.model = hmm.GaussianHMM(
            n_components=self.n_components,
            covariance_type="full",
            n_iter=100,
            random_state=self.random_state
        )
        
        self.model.fit(X_arr)
        
        # Enforce consistent state sorting (State 0 = Calm/Low Vol, State 1 = Stressed/High Vol)
        # Compare means of Log_Rolling_Vol
        mean_0 = self.model.means_[0][0]
        mean_1 = self.model.means_[1][0]
        
        if mean_0 > mean_1:
            print("Sorting HMM states: swapping State 0 and State 1 to make State 0 low-volatility.")
            # Swap means
            self.model.means_ = self.model.means_[::-1]
            # Swap covars
            self.model.covars_ = self.model.covars_[::-1]
            # Swap transition matrix rows and columns
            trans = self.model.transmat_.copy()
            trans = trans[[1, 0], :]
            trans = trans[:, [1, 0]]
            self.model.transmat_ = trans
            # Swap start probabilities
            self.model.startprob_ = self.model.startprob_[::-1]
            
        return self

    def predict(self, X):
        """
        Predicts discrete regime labels (0 or 1).
        """
        if isinstance(X, pd.DataFrame):
            if 'Log_Rolling_Vol' in X.columns:
                X_arr = X[['Log_Rolling_Vol']].dropna().values
            else:
                X_arr = np.log(X[['Rolling_Vol']]).dropna().values
        else:
            X_arr = X
        return self.model.predict(X_arr)

    def predict_proba(self, X):
        """
        Predicts regime probabilities. Returns an array of shape (N, n_components).
        """
        if isinstance(X, pd.DataFrame):
            if 'Log_Rolling_Vol' in X.columns:
                X_arr = X[['Log_Rolling_Vol']].dropna().values
            else:
                X_arr = np.log(X[['Rolling_Vol']]).dropna().values
        else:
            X_arr = X
        return self.model.predict_proba(X_arr)
