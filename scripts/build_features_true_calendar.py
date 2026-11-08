"""Recompute Bank Nifty expiry-cycle features (Days_To_Expiry, Expiry_Week, sin/cos) from the TRUE
monthly expiry dates in the Bhavcopy, saving data/interim/banknifty_features_true.parquet."""
import pandas as pd
from src import config
from src.features import calculate_expiry_distance, cyclical_encode_distance

df = pd.read_parquet(config.INTERIM_DATA_DIR / "banknifty_features.parquet")
ex = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_dates.parquet")
dates = ex[(ex.Symbol == "BANKNIFTY") & ex.IsMonthly].ExpiryDate
df = df.drop(columns=["Days_To_Expiry", "Expiry_Week", "Expiry_Dist_Sin", "Expiry_Dist_Cos"])
df = cyclical_encode_distance(calculate_expiry_distance(df, dates))
df.to_parquet(config.INTERIM_DATA_DIR / "banknifty_features_true.parquet", index=False)
print(len(df), df.Expiry_Week.mean())
