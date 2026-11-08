"""Sanity tests on the derived panels (run: python -m pytest tests -q). They guard the errors found in the review."""
import pandas as pd, pytest
from src import config
from src.regime_calendar import tag_expiry_regime, REGIME_NAMES

I = config.INTERIM_DATA_DIR


@pytest.fixture(scope="module")
def ex():
    return pd.read_parquet(I / "index_expiry_dates.parquet")


def test_true_expiries_match_known_dates(ex):
    bn = set(ex[(ex.Symbol == "BANKNIFTY") & ex.IsMonthly].ExpiryDate)
    assert pd.Timestamp("2025-01-30") in bn and pd.Timestamp("2025-01-29") not in bn      # Thursday, not Wednesday
    nf = set(ex[(ex.Symbol == "NIFTY") & ex.IsMonthly].ExpiryDate)
    assert pd.Timestamp("2024-09-26") in nf                                                # Nifty expired Thursdays in 2024


def test_one_monthly_expiry_per_month_after_reform(ex):
    bn = ex[(ex.Symbol == "BANKNIFTY") & ex.IsMonthly & (ex.ExpiryDate >= "2024-12-01")]
    assert bn.groupby(bn.ExpiryDate.dt.to_period("M")).size().max() == 1
    weekly = ex[(ex.Symbol == "BANKNIFTY") & (ex.ExpiryDate > "2024-11-13")]
    assert len(weekly) == weekly.IsMonthly.sum()                                           # no non-monthly expiries after 2024-11-13


def test_regimes_partition_dates():
    s = tag_expiry_regime(pd.to_datetime(["2020-01-02", "2023-09-06", "2024-11-14", "2025-09-01"]))
    assert list(s) == REGIME_NAMES


def test_monthly_panel_integrity():
    m = pd.read_parquet(I / "monthly_expiry_panel_all.parquet")
    assert set(m.Symbol) == {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"}
    assert ((m.share.dropna() >= 0) & (m.share.dropna() <= 1.0001)).all()


def test_placebo_group_not_collapsed():
    st = pd.read_parquet(I / "stock_fo_daily.parquet"); st["ym"] = st.Date.dt.to_period("M")
    v = st.groupby("ym")[["Value_StockOpt", "Value_StockFut"]].sum().sum(axis=1)
    assert 0.5 < v.loc["2025-01":"2026-09"].mean() / v.loc["2024-01":"2024-09"].mean() < 1.5
