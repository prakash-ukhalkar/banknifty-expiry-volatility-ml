"""
Data Loader module for fetching and loading Bank Nifty daily OHLCV and calendar data.
"""
import os
import calendar
import pandas as pd
import yfinance as yf
from pathlib import Path
from . import config

def fetch_banknifty_data(start_date=config.START_DATE, end_date=config.END_DATE):
    """
    Fetches daily Bank Nifty OHLCV data from Yahoo Finance (^NSEBANK) and saves it to raw data.
    """
    print(f"Downloading ^NSEBANK data from {start_date} to {end_date}...")
    df = yf.download("^NSEBANK", start=start_date, end=end_date)
    
    # Reset index to have 'Date' as a column
    df = df.reset_index()
    
    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
        
    # Save to data/raw/
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = config.RAW_DATA_DIR / "banknifty_ohlcv_2023_2026.csv"
    df.to_csv(raw_path, index=False)
    print(f"Saved raw Bank Nifty data to {raw_path}")
    return df

def generate_expiry_calendar(trading_dates):
    """
    Generates the Bank Nifty monthly expiry calendar based on regulatory rules:
    - Before March 2024: Last Thursday of the month
    - March 2024 - August 2025: Last Wednesday of the month
    - September 2025 - June 2026: Last Tuesday of the month
    
    Adjusts for trading holidays by moving to the previous trading day.
    """
    trading_dates_set = set(pd.to_datetime(trading_dates).date)
    
    # Create date range for each month from mid-2023 to mid-2026
    start_dt = pd.to_datetime(config.START_DATE)
    end_dt = pd.to_datetime(config.END_DATE)
    
    months = pd.date_range(start=start_dt, end=end_dt, freq="MS") # Month Start
    
    expiry_records = []
    
    for m in months:
        year = m.year
        month = m.month
        
        # Determine the target weekday index (Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, etc.)
        # Rule selection
        if (year < 2024) or (year == 2024 and month < 3):
            # Before March 2024: Last Thursday (3)
            target_weekday = 3
            rule_name = "Last Thursday"
        elif (year < 2025) or (year == 2025 and month < 9):
            # March 2024 - August 2025: Last Wednesday (2)
            target_weekday = 2
            rule_name = "Last Wednesday"
        else:
            # September 2025 - Present: Last Tuesday (1)
            target_weekday = 1
            rule_name = "Last Tuesday"
            
        # Get all days in the month
        last_day = calendar.monthrange(year, month)[1]
        month_days = pd.date_range(start=f"{year}-{month:02d}-01", end=f"{year}-{month:02d}-{last_day}")
        
        # Filter for the target weekday
        target_days = month_days[month_days.weekday == target_weekday]
        scheduled_expiry = target_days[-1].date()
        
        # Adjust for holidays by rolling backward to the nearest valid trading day
        import datetime
        actual_expiry = scheduled_expiry
        max_trading_date = max(trading_dates_set) if trading_dates_set else None
        while True:
            if max_trading_date and actual_expiry > max_trading_date:
                # If the expiry date is in the future (beyond our dataset),
                # assume it is a trading day if it falls on a weekday.
                if actual_expiry.weekday() < 5:
                    break
                else:
                    actual_expiry = actual_expiry - datetime.timedelta(days=1)
            else:
                # If historical, it must exist in the trading dates set
                if actual_expiry in trading_dates_set:
                    break
                else:
                    actual_expiry = actual_expiry - datetime.timedelta(days=1)
            
            # Prevent infinite loops in case of errors
            if (scheduled_expiry - actual_expiry).days > 10:
                break
                
        expiry_records.append({
            "Year": year,
            "Month": month,
            "ScheduledExpiry": scheduled_expiry.strftime("%Y-%m-%d"),
            "ActualExpiry": actual_expiry.strftime("%Y-%m-%d"),
            "Rule": rule_name,
            "HolidayAdjusted": 1 if actual_expiry != scheduled_expiry else 0
        })
        
    df_expiry = pd.DataFrame(expiry_records)
    expiry_path = config.RAW_DATA_DIR / "nse_expiry_calendar.csv"
    df_expiry.to_csv(expiry_path, index=False)
    print(f"Generated and saved expiry calendar to {expiry_path}")
    return df_expiry

def generate_holiday_list(trading_dates):
    """
    Identifies trading holidays (weekdays Mon-Fri where market was closed)
    and saves them to data/raw/nse_holidays.csv.
    """
    start_dt = pd.to_datetime(config.START_DATE)
    end_dt = pd.to_datetime(config.END_DATE)
    
    # Generate all weekdays in the range
    all_days = pd.date_range(start=start_dt, end=end_dt)
    weekdays = all_days[all_days.weekday < 5] # Mon-Fri
    trading_dates_set = set(pd.to_datetime(trading_dates).date)
    
    holidays = []
    for d in weekdays:
        d_date = d.date()
        if d_date not in trading_dates_set:
            # Check if this weekday is a holiday (not traded)
            holidays.append({
                "Date": d_date.strftime("%Y-%m-%d"),
                "DayOfWeek": d.day_name()
            })
            
    df_holidays = pd.DataFrame(holidays)
    holiday_path = config.RAW_DATA_DIR / "nse_holidays.csv"
    df_holidays.to_csv(holiday_path, index=False)
    print(f"Identified and saved {len(df_holidays)} holidays to {holiday_path}")
    return df_holidays

def load_data_pipeline():
    """
    Orchestrates downloading data, generating the calendars, and preparing the raw data structures.
    """
    df_ohlcv = fetch_banknifty_data()
    # Handle multi-level columns from yfinance if present (newer yfinance versions sometimes return multi-level df)
    # yfinance often returns MultiIndex columns for symbols if not cleaned
    if isinstance(df_ohlcv.columns, pd.MultiIndex):
        # Flatten MultiIndex columns
        df_ohlcv.columns = [col[0] if col[1] == '' else col[0] for col in df_ohlcv.columns]
    
    # Ensure Date column is datetime
    df_ohlcv['Date'] = pd.to_datetime(df_ohlcv['Date']).dt.date
    
    trading_dates = df_ohlcv['Date'].tolist()
    
    df_expiry = generate_expiry_calendar(trading_dates)
    df_holidays = generate_holiday_list(trading_dates)
    
    return df_ohlcv, df_expiry, df_holidays
