"""Submission figures for Empirical Economics: no titles inside the figure (captions go in the manuscript), Arial/Helvetica lettering,
line styles + markers (not colour alone), PNG at 600 dpi and vector PDF. Output: manuscript/empirical-economics-files/figures/Fig1..Fig5"""
import json
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, statsmodels.formula.api as smf
from src import config

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 9, "axes.linewidth": 0.8})
OUT = config.PROJECT_ROOT / "manuscript" / "empirical-economics-files" / "figures" if hasattr(config, "PROJECT_ROOT") else None
if OUT is None:
    from pathlib import Path
    OUT = Path(__file__).resolve().parent.parent / "manuscript" / "empirical-economics-files" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
cut = pd.Timestamp("2024-11-14")
ma = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet")
ma = ma[(ma.ym >= pd.Period("2023-01")) & (ma.ym < pd.Period("2026-10")) & (ma.tot > 0)].copy(); ma["t"] = ma.ym.dt.to_timestamp()
STY = {"NIFTY": ("-", "o", "0.0"), "SENSEX": ("-", "s", "0.35"), "BANKNIFTY": ("--", "^", "0.0"), "FINNIFTY": ("--", "v", "0.35"),
       "MIDCPNIFTY": (":", "D", "0.0"), "BANKEX": (":", "x", "0.35")}


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=600, bbox_inches="tight"); fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight"); plt.close(fig)


# Fig1: turnover and expiry-day share
fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.1))
for s, g in ma.groupby("Symbol"):
    ls, mk, c = STY[s]
    ax[0].plot(g.t, g.tot, ls=ls, color=c, marker=mk, ms=2.5, lw=1.1, label=s.title() if False else s)
    gg = g.dropna(subset=["share"]); ax[1].plot(gg.t, gg.share, ls=ls, color=c, marker=mk, ms=2.5, lw=1.1)
import matplotlib.dates as mdates
for a in ax:
    a.axvline(cut, color="k", lw=0.7, ls="-."); a.xaxis.set_major_locator(mdates.YearLocator()); a.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax[0].set_yscale("log"); ax[0].set_ylabel("Monthly F&O turnover (INR, log scale)"); ax[1].set_ylabel("Expiry-day share of monthly turnover"); ax[1].set_ylim(0, 1)
ax[0].text(0.02, 0.04, "(a)", transform=ax[0].transAxes); ax[1].text(0.02, 0.93, "(b)", transform=ax[1].transAxes)
ax[0].set_ylim(1e8, 3e17); ax[0].legend(fontsize=6.5, ncol=3, frameon=False, loc="upper center"); fig.tight_layout(); save(fig, "Fig1")

# Fig2: timing and never-weekly placebo (Sep 2024 = 100)
st = pd.read_parquet(config.INTERIM_DATA_DIR / "stock_fo_daily.parquet"); st["ym"] = st.Date.dt.to_period("M")
pm = ma.pivot(index="ym", columns="Symbol", values="tot"); pm["Stock F&O (never weekly)"] = st.groupby("ym")[["Value_StockOpt", "Value_StockFut"]].sum().sum(axis=1)
w = pm.loc["2024-03":"2025-09"]; w = w / w.loc["2024-09"] * 100
fig, ax = plt.subplots(figsize=(4.6, 3.1))
for c_ in ["BANKNIFTY", "FINNIFTY", "BANKEX", "NIFTY", "SENSEX", "Stock F&O (never weekly)"]:
    ls, mk, col = STY.get(c_, ("-", "*", "0.0"))
    ax.plot(w.index.to_timestamp(), w[c_], ls=ls, color=col, marker=mk, ms=2.5, lw=2.0 if "Stock" in c_ else 1.1, label=c_)
import matplotlib.dates as mdates
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y")); ax.tick_params(axis="x", rotation=30)
ax.axvline(cut, color="k", lw=0.7, ls="-."); ax.set_yscale("log"); ax.set_ylabel("Monthly turnover, Sep 2024 = 100 (log scale)"); ax.legend(fontsize=6.5, frameon=False)
fig.tight_layout(); save(fig, "Fig4")

# Fig3: quarterly event study, Bank Nifty vs Nifty
m = ma[(ma.Symbol.isin(["BANKNIFTY", "NIFTY"])) & (ma.exp_day > 0) & (ma.ym != pd.Period("2024-11"))].copy()
m["bn"] = (m.Symbol == "BANKNIFTY").astype(int); m["q"] = ((m.t.dt.year - 2024) * 4 + (m.t.dt.quarter - 4)).clip(-8, 6)
m["lt"], m["ls"] = np.log(m.tot), np.log(m.share)
fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.0))
for a, y, lab in [(ax[0], "lt", "Log total turnover"), (ax[1], "ls", "Log expiry-day share")]:
    r = smf.ols(f"{y} ~ C(q, Treatment(-1)):bn + C(q) + bn", m).fit(cov_type="HC1")
    ks = [k for k in r.params.index if ":bn" in k]; qs = np.array([float(k.split("[T.")[1].split("]")[0]) for k in ks]); o = np.argsort(qs)
    est = r.params[ks].values[o]; ci = r.conf_int().loc[ks].values[o]
    a.errorbar(qs[o], est, yerr=[est - ci[:, 0], ci[:, 1] - est], fmt="o", color="k", capsize=2, ms=3, lw=0.8)
    a.axhline(0, color="0.5", lw=0.6); a.axvline(-0.5, color="k", lw=0.7, ls="-."); a.set_xlabel("Quarters relative to 2024Q4"); a.set_ylabel(lab)
ax[0].text(0.03, 0.05, "(a)", transform=ax[0].transAxes); ax[1].text(0.03, 0.9, "(b)", transform=ax[1].transAxes); fig.tight_layout(); save(fig, "Fig2")

# Fig4: expiry-day turnover multiple profile
p = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet"); ex = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_dates.parquet")
fig, ax = plt.subplots(figsize=(4.6, 3.1))
for s, mk in [("BANKNIFTY", "^"), ("NIFTY", "o")]:
    b = p[p.Symbol == s].set_index("Date").Value_Total.dropna(); idx = list(b.index)
    for lab, a0, z0, ls in [("before", "2023-01-01", "2024-09-30", "-"), ("after", "2025-01-01", "2026-09-30", "--")]:
        e = ex[(ex.Symbol == s) & ex.IsMonthly & (ex.ExpiryDate >= a0) & (ex.ExpiryDate <= z0)].ExpiryDate; prof = []
        for d0 in e:
            if d0 not in b.index: continue
            i = idx.index(d0)
            if i < 3 or i + 3 >= len(idx): continue
            prof.append(b.iloc[i - 3:i + 4].values / np.median(b.iloc[max(0, i - 25):i - 3].values))
        ax.plot(range(-3, 4), np.median(prof, axis=0), ls=ls, marker=mk, color="0.0" if s == "BANKNIFTY" else "0.4", ms=3.5, lw=1.1, label=f"{s.title().replace('nifty', ' Nifty')} {lab} reform")
ax.set_yscale("log"); ax.set_xlabel("Trading days from monthly expiry"); ax.set_ylabel("Turnover / prior-month median day"); ax.legend(fontsize=6.5, frameon=False); fig.tight_layout(); save(fig, "Fig3")

# Fig5: pre-trend sensitivity (identified set by smoothness bound M, in multiples of pre-period roughness)
r = json.load(open(config.RESULTS_DIR / "pretrend_sensitivity.json"))["NSE: BANKNIFTY vs NIFTY"]
fig, ax = plt.subplots(1, 2, figsize=(7.2, 3.0))
for a, y, lab in [(ax[0], "ls", "Expiry-day share (log points)"), (ax[1], "lt", "Total turnover (log points)")]:
    g = np.array(r[y]["grid"]); a.fill_between(g[:, 0], g[:, 1], g[:, 2], color="0.8"); a.plot(g[:, 0], g[:, 1], "k-", lw=0.8); a.plot(g[:, 0], g[:, 2], "k-", lw=0.8)
    a.axhline(0, color="k", ls=":", lw=0.8); a.axhline(r[y]["theta_naive"], color="k", ls="--", lw=0.8); a.set_xlabel("Smoothness bound M (multiples of $M_{pre}$)"); a.set_ylabel(lab)
ax[0].text(0.03, 0.92, "(a)", transform=ax[0].transAxes); ax[1].text(0.03, 0.92, "(b)", transform=ax[1].transAxes); fig.tight_layout(); save(fig, "Fig5")
print(sorted(x.name for x in OUT.glob("*.png")))
