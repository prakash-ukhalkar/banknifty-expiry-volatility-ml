"""
Plotting module to enforce consistent styling across all project figures.
"""
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

def set_style():
    """
    Sets the global matplotlib and seaborn style configuration for publication-quality figures.
    """
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.titlesize": 14,
        "figure.dpi": 300,
        "savefig.dpi": 300
    })

def plot_regimes(df, date_col='Date', price_col='Close', regime_col='Regime'):
    """
    Plots the price history colored/shaded by HMM volatility regime.
    """
    df_plot = df.copy().sort_values(date_col)
    df_plot[date_col] = pd.to_datetime(df_plot[date_col])
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot[date_col], df_plot[price_col], color='black', linewidth=1.5, label='Bank Nifty Close')
    
    # Shade background by regime
    # Create contiguous blocks of the same regime
    regimes = df_plot[regime_col].values
    dates = df_plot[date_col].values
    
    # Shade high vol regime (1) in red/coral and low vol (0) in blue/grey
    # We can do this day-by-day with fill_between or spans
    i = 0
    while i < len(regimes):
        start_date = dates[i]
        curr_regime = regimes[i]
        
        # find end of block
        j = i
        while j < len(regimes) and regimes[j] == curr_regime:
            j += 1
            
        end_date = dates[j-1]
        
        # Color mapping: State 0 = Calm (Soft Green/Grey), State 1 = Stressed (Soft Coral/Red)
        color = '#FADBD8' if curr_regime == 1 else '#EAFAF1'
        label = 'Stressed (High Vol)' if curr_regime == 1 else 'Calm (Low Vol)'
        
        # Add span
        ax.axvspan(start_date, end_date, color=color, alpha=0.6, label=label if i == 0 or (curr_regime == 1 and not ax.get_legend_handles_labels()[1].count('Stressed (High Vol)')) or (curr_regime == 0 and not ax.get_legend_handles_labels()[1].count('Calm (Low Vol)')) else "")
        
        i = j
        
    ax.set_title("Bank Nifty Price Chart with HMM Volatility Regimes", fontsize=14, fontweight='bold')
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Close Price (INR)", fontsize=12)
    
    # Handle legends to avoid duplicates
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='upper left', frameon=True, facecolor='white')
    
    plt.tight_layout()
    return fig

def plot_feature_importance(importance_df, title="Feature Importance (XGBoost)"):
    """
    Plots feature importances using consistent styling.
    importance_df should have columns: 'Feature' and 'Importance'.
    """
    importance_df = importance_df.sort_values(by='Importance', ascending=False)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        x='Importance', 
        y='Feature', 
        data=importance_df, 
        palette='viridis', 
        ax=ax
    )
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel("Feature Importance", fontsize=12)
    ax.set_ylabel("Features", fontsize=12)
    
    plt.tight_layout()
    return fig

def plot_error_distribution(errors_dict):
    """
    Plots distribution of prediction errors for baseline vs proposed model.
    errors_dict format: {'Model Name': array_of_errors, ...}
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = {'Baseline Model': '#1f77b4', 'Proposed Model': '#ff7f0e'}
    
    for model_name, errors in errors_dict.items():
        color = colors.get(model_name, None)
        sns.kdeplot(
            errors, 
            label=model_name, 
            fill=True, 
            alpha=0.4, 
            linewidth=2,
            color=color,
            ax=ax
        )
        
    ax.axvline(0, color='grey', linestyle='--', linewidth=1.5, label='Zero Error')
    ax.set_title("Comparison of Forecast Error Distributions", fontsize=14, fontweight='bold')
    ax.set_xlabel("Prediction Error (Actual Return - Predicted Return)", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.legend(loc='upper right', frameon=True, facecolor='white')
    
    plt.tight_layout()
    return fig
