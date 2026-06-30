"""
Evaluation metrics including RMSE, MAE, directional accuracy, and the Diebold-Mariano test.
"""
import numpy as np
from scipy.stats import norm

def calculate_metrics(y_true, y_pred):
    """
    Returns a dictionary of RMSE, MAE, and directional accuracy.
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    mae = np.mean(np.abs(y_true - y_pred))
    
    # Directional accuracy: sign matches (excluding exact zeros to prevent bias)
    # A true change of 0 and pred of 0 is counted as correct, but in returns it's rarely exact 0.
    correct_direction = np.sign(y_true) == np.sign(y_pred)
    directional_acc = np.mean(correct_direction)
    
    return {
        "RMSE": float(rmse),
        "MAE": float(mae),
        "Directional_Accuracy": float(directional_acc)
    }

def diebold_mariano_test(y_true, y_pred1, y_pred2, h=1, power=2):
    """
    Computes the Diebold-Mariano test statistic and p-value to compare forecast accuracy.
    
    Parameters:
    y_true : 1D array of true values
    y_pred1 : 1D array of forecasts from Model 1 (Baseline)
    y_pred2 : 1D array of forecasts from Model 2 (Proposed)
    h : Forecast horizon (default 1)
    power : Loss function exponent (default 2 for MSE, 1 for MAE)
    
    Returns:
    dm_stat : Diebold-Mariano statistic
    p_value_two_sided : Two-sided p-value
    p_value_one_sided : One-sided p-value (H1: Model 2 is more accurate than Model 1)
    """
    y_true = np.array(y_true)
    y_pred1 = np.array(y_pred1)
    y_pred2 = np.array(y_pred2)
    
    T = len(y_true)
    
    # Loss differential
    if power == 1:
        d = np.abs(y_true - y_pred1) - np.abs(y_true - y_pred2)
    elif power == 2:
        d = (y_true - y_pred1)**2 - (y_true - y_pred2)**2
    else:
        raise ValueError("Power must be 1 (MAE) or 2 (MSE)")
        
    d_mean = np.mean(d)
    
    # Compute autocovariances for Newey-West style variance estimator
    # We sum autocovariances up to lag h-1
    gamma = []
    for k in range(h):
        if k == 0:
            gamma.append(np.var(d, ddof=0))
        else:
            # Covariance at lag k
            gamma.append(np.mean((d[k:] - d_mean) * (d[:-k] - d_mean)))
            
    # Variance of the sum of d
    var_d = gamma[0] + 2 * sum(gamma[1:])
    
    # Avoid division by zero
    if var_d <= 1e-12:
        dm_stat = 0.0
        p_value_two_sided = 1.0
        p_value_one_sided = 0.5
    else:
        dm_stat = d_mean / np.sqrt(var_d / T)
        p_value_two_sided = 2.0 * (1.0 - norm.cdf(np.abs(dm_stat)))
        p_value_one_sided = 1.0 - norm.cdf(dm_stat)
        
    return {
        "DM_Stat": float(dm_stat),
        "P_Value_Two_Sided": float(p_value_two_sided),
        "P_Value_One_Sided": float(p_value_one_sided)
    }

def backtest_trading_strategy(y_true, y_pred, cost_rate=0.0002):
    """
    Backtests a simple long/short strategy based on return predictions.
    
    Parameters:
    y_true: 1D array of actual returns
    y_pred: 1D array of predicted returns
    cost_rate: Transaction cost rate per trade (default 0.02% or 2 bps)
    
    Returns:
    metrics: Dict containing Sharpe, Sortino, Max Drawdown, and cumulative returns
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    # Position: +1 if pred > 0, -1 if pred < 0, 0 otherwise
    positions = np.sign(y_pred)
    
    # Daily raw returns of the strategy
    strategy_returns_raw = positions * y_true
    
    # Calculate transaction costs on turnover
    # Position changes: diff of positions
    position_changes = np.zeros_like(positions)
    position_changes[0] = np.abs(positions[0])  # Cost to enter first position
    position_changes[1:] = np.abs(position_changes[1:] - position_changes[:-1]) if len(position_changes) > 1 else 0.0
    # Wait, the correct calculation is on the positions difference:
    # positions change is np.abs(positions[1:] - positions[:-1])
    position_changes[1:] = np.abs(positions[1:] - positions[:-1])
    
    transaction_costs = position_changes * cost_rate
    strategy_returns_net = strategy_returns_raw - transaction_costs
    
    # Cumulative returns
    cum_returns = np.exp(np.cumsum(strategy_returns_net)) - 1
    buy_hold_cum = np.exp(np.cumsum(y_true)) - 1
    
    # Performance metrics
    mean_net = np.mean(strategy_returns_net)
    std_net = np.std(strategy_returns_net)
    
    # Sharpe Ratio (annualized)
    if std_net > 1e-9:
        sharpe = (mean_net / std_net) * np.sqrt(252)
    else:
        sharpe = 0.0
        
    # Sortino Ratio (annualized)
    downside_returns = strategy_returns_net[strategy_returns_net < 0]
    if len(downside_returns) > 0:
        std_downside = np.std(downside_returns)
        if std_downside > 1e-9:
            sortino = (mean_net / std_downside) * np.sqrt(252)
        else:
            sortino = 0.0
    else:
        sortino = 0.0
        
    # Max Drawdown
    cum_equity = np.exp(np.cumsum(strategy_returns_net))
    running_max = np.maximum.accumulate(cum_equity)
    drawdowns = (cum_equity - running_max) / (running_max + 1e-9)
    max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0.0
    
    return {
        "Annualized_Return": float(mean_net * 252),
        "Annualized_Vol": float(std_net * np.sqrt(252)),
        "Sharpe_Ratio": float(sharpe),
        "Sortino_Ratio": float(sortino),
        "Max_Drawdown": float(max_drawdown),
        "Total_Return": float(cum_returns[-1]) if len(cum_returns) > 0 else 0.0,
        "Buy_Hold_Return": float(buy_hold_cum[-1]) if len(buy_hold_cum) > 0 else 0.0,
        "Net_Returns": strategy_returns_net.tolist()
    }
