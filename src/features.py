"""
Feature engineering module for technical indicators and cyclical expiry distance.
"""
import pandas as pd
import numpy as np

def add_technical_indicators(df):
    """
    Appends standard technical indicators (RSI, MACD, Bollinger Bands, ATR, Rolling Vol) to the DataFrame.
    Assumes df has columns: Open, High, Low, Close, Volume.
    """
    df = df.copy()
    
    # Daily returns
    df['Return'] = np.log(df['Close'] / df['Close'].shift(1))
    
    # 1. RSI (Relative Strength Index) - 14 period
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    # Use exponential moving average for average gains and losses
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 2. MACD (Moving Average Convergence Divergence)
    ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # 3. Bollinger Bands - 20 period, 2 std
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Mid'] - 2 * bb_std
    df['BB_PctB'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'] + 1e-9)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / (df['BB_Mid'] + 1e-9)
    
    # 4. ATR (Average True Range) - 14 period
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift(1))
    low_cp = np.abs(df['Low'] - df['Close'].shift(1))
    
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    
    # 5. Rolling Volatility - 10-day rolling std of returns
    df['Rolling_Vol'] = df['Return'].rolling(window=10).std()

    # 6. Range-based realized volatility estimators (Parkinson, Garman-Klass).
    # Close-to-close rolling std above only uses the daily close and is ~5x less
    # statistically efficient than range-based estimators that also use the day's
    # high/low (and open), since it discards most of the intraday price path.
    # Parkinson (1980): sigma^2 = (1 / (4*ln(2))) * E[(ln(H/L))^2]
    log_hl = np.log(df['High'] / df['Low'])
    df['Parkinson_Vol_1d'] = np.sqrt((1.0 / (4.0 * np.log(2.0))) * (log_hl ** 2))
    df['Parkinson_Vol_10d'] = np.sqrt(
        (1.0 / (4.0 * np.log(2.0))) * (log_hl ** 2).rolling(window=10).mean()
    )
    # Garman-Klass (1980): adds open/close terms, more efficient still.
    log_co = np.log(df['Close'] / df['Open'])
    gk_term = 0.5 * (log_hl ** 2) - (2 * np.log(2) - 1) * (log_co ** 2)
    df['GarmanKlass_Vol_1d'] = np.sqrt(gk_term.clip(lower=0))
    df['GarmanKlass_Vol_10d'] = np.sqrt(gk_term.rolling(window=10).mean().clip(lower=0))

    return df

def calculate_expiry_distance(df, expiry_dates):
    """
    Calculates the distance in trading days to the next monthly expiry date.
    df: DataFrame containing a 'Date' column
    expiry_dates: list or set of actual expiry dates (datetime.date or string)
    """
    df = df.copy()
    df['Date_dt'] = pd.to_datetime(df['Date']).dt.date
    
    # Parse expiry dates into sorted list of datetime.date objects
    expiries_parsed = sorted(list(pd.to_datetime(list(expiry_dates)).date))
    
    # Get all trading dates in order
    trading_dates = df['Date_dt'].tolist()
    date_to_idx = {date: idx for idx, date in enumerate(trading_dates)}
    
    days_to_expiry = []
    expiry_week_flag = []
    
    for current_date in trading_dates:
        # Find the next expiry date that is >= current_date
        next_expiry = None
        for exp in expiries_parsed:
            if exp >= current_date:
                next_expiry = exp
                break
                
        if next_expiry is not None:
            # Distance in trading days
            current_idx = date_to_idx[current_date]
            
            # If the next_expiry is in the trading dates, we count index difference.
            # If next_expiry is not in our data (e.g. at the end of the dataset), we estimate.
            if next_expiry in date_to_idx:
                expiry_idx = date_to_idx[next_expiry]
                dist = expiry_idx - current_idx
            else:
                # Fallback: calendar days (not perfect, but safe for edge cases)
                dist = np.busday_count(current_date, next_expiry)
        else:
            # Fallback if no future expiry exists in the list
            dist = 20 # default representation of a full cycle
            
        days_to_expiry.append(dist)
        # Expiry week flag: 1 if distance is <= 4 trading days, else 0
        expiry_week_flag.append(1 if dist <= 4 else 0)
        
    df['Days_To_Expiry'] = days_to_expiry
    df['Expiry_Week'] = expiry_week_flag
    
    # Drop temp column
    df = df.drop(columns=['Date_dt'])
    return df

def cyclical_encode_distance(df, max_cycle=20.0):
    """
    Encodes the 'Days_To_Expiry' column using sine and cosine transformations.
    """
    df = df.copy()
    df['Expiry_Dist_Sin'] = np.sin(2 * np.pi * df['Days_To_Expiry'] / max_cycle)
    df['Expiry_Dist_Cos'] = np.cos(2 * np.pi * df['Days_To_Expiry'] / max_cycle)
    return df

def add_all_features(df, expiry_dates):
    """
    Combines technical indicators, expiry distance features, and cyclical encoding.
    """
    df = add_technical_indicators(df)
    df = calculate_expiry_distance(df, expiry_dates)
    df = cyclical_encode_distance(df)
    return df
