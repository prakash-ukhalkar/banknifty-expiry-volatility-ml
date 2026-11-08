"""Figures for the corrected design (true expiry dates). Writes results/figures/*.png (300 dpi)."""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, statsmodels.formula.api as smf
from src import config

out = config.RESULTS_DIR / "figures"; out.mkdir(exist_ok=True)
m = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel.parquet")
m = m[m.ym < pd.Period("2026-10")]  # Oct-2026 is a partial month (data ends 16 Oct)
m["t"] = m["ym"].dt.to_timestamp(); cut = pd.Timestamp("2024-11-14")
col = {"NIFTY": "#1f77b4", "BANKNIFTY": "#d62728", "FINNIFTY": "#ff7f0e", "MIDCPNIFTY": "#2ca02c"}

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for s, g in m.groupby("Symbol"):
    g = g[g.tot > 0]
    ax[0].plot(g.t, g.tot, label=s, color=col[s]); ax[1].plot(g.t, g.share, label=s, color=col[s])
for a in ax: a.axvline(cut, ls=":", c="k")
ax[0].set_yscale("log"); ax[0].set_title("(a) Monthly F&O turnover (INR, log)"); ax[1].set_title("(b) Monthly-expiry-day share of month's turnover")
ax[1].set_ylim(0, 0.8); ax[0].legend(fontsize=8); fig.tight_layout(); fig.savefig(out / "fig1_turnover_and_share.png", dpi=300); plt.close(fig)

d = m[m.Symbol.isin(["BANKNIFTY", "NIFTY"]) & (m.exp_day > 0) & (m.tot > 0) & (m.ym != pd.Period("2024-11"))].copy()
d["bn"] = (d.Symbol == "BANKNIFTY").astype(int)
d["q"] = ((d.t.dt.year - 2024) * 4 + (d.t.dt.quarter - 4)).clip(-8, 6)
d["lt"], d["ls"] = np.log(d.tot), np.log(d.share)
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for a, y, ttl in [(ax[0], "lt", "(a) log total turnover"), (ax[1], "ls", "(b) log expiry-day share")]:
    r = smf.ols(f"{y} ~ C(q, Treatment(-1)):bn + C(q) + bn", d).fit(cov_type="HC1")
    ks = [k for k in r.params.index if ":bn" in k]; qs = [float(k.split("[T.")[1].split("]")[0]) for k in ks]
    ci = r.conf_int().loc[ks]; o = np.argsort(qs)
    qs = np.array(qs)[o]; est = r.params[ks].values[o]
    a.errorbar(qs, est, yerr=[est - ci[0].values[o], ci[1].values[o] - est], fmt="o", c="#d62728", capsize=2)
    a.axhline(0, c="k", lw=.5); a.axvline(-0.5, ls=":", c="k"); a.set_title(ttl + " (Bank Nifty vs Nifty, ref. 2023Q4)"); a.set_xlabel("Quarters from 2024Q4")
fig.tight_layout(); fig.savefig(out / "fig2_event_study.png", dpi=300); plt.close(fig)
print("saved", list(out.glob("*.png")))

# Fig 3: walk-forward directional accuracy on the true calendar --------------------------------
import json
w = json.load(open(config.RESULTS_DIR / "walk_forward_results_true_calendar.json"))["pooled_significance"]
conds = ["Baseline (Technical Only)", "Baseline + Expiry", "Baseline + Regime", "Proposed (Combined)"]
mu = np.array([w[f"DirAcc_CI_{c}"]["accuracy_mean"] for c in conds]) * 100
lo = mu - np.array([w[f"DirAcc_CI_{c}"]["ci_2.5"] for c in conds]) * 100
hi = np.array([w[f"DirAcc_CI_{c}"]["ci_97.5"] for c in conds]) * 100 - mu
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.bar(range(4), mu, yerr=[lo, hi], capsize=4, color="#4477AA", alpha=.85); ax.axhline(50, c="k", ls="--", label="Chance (50%)")
ax.set_xticks(range(4)); ax.set_xticklabels(["Technical", "+Expiry", "+Regime", "Combined"]); ax.set_ylim(40, 60)
ax.set_ylabel("Pooled out-of-fold directional accuracy (%)"); ax.set_title(f"Walk-forward accuracy, true calendar (n={w['Binomial_vs_50pct_Baseline (Technical Only)']['n_total']} days)")
ax.legend(); fig.tight_layout(); fig.savefig(out / "fig3_walk_forward_true_calendar.png", dpi=300); plt.close(fig)

# Fig 4: Bank Nifty turnover around TRUE monthly expiry days, weekly-era vs monthly-only era --
p = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_panel.parquet")
ex = pd.read_parquet(config.INTERIM_DATA_DIR / "index_expiry_dates.parquet")
fig, ax = plt.subplots(figsize=(7, 4.5))
for s, c in [("BANKNIFTY", "#d62728"), ("NIFTY", "#1f77b4")]:
    b = p[p.Symbol == s].set_index("Date").Value_Total.dropna(); idx = list(b.index)
    for lab, a, z, ls in [("pre", "2023-01-01", "2024-09-30", "-"), ("post", "2025-01-01", "2026-09-30", "--")]:
        e = ex[(ex.Symbol == s) & ex.IsMonthly & (ex.ExpiryDate >= a) & (ex.ExpiryDate <= z)].ExpiryDate
        prof = []
        for d0 in e:
            if d0 not in b.index: continue
            i = idx.index(d0)
            if i < 3 or i + 3 >= len(idx): continue
            v = b.iloc[i - 3:i + 4].values; prof.append(v / np.median(b.iloc[max(0, i - 25):i - 3].values))
        ax.plot(range(-3, 4), np.median(prof, axis=0), ls, c=c, marker="o", label=f"{s} {lab} reform")
ax.set_yscale("log"); ax.set_xlabel("Trading days from true monthly expiry"); ax.set_ylabel("Turnover / prior-month median day")
ax.set_title("Expiry-day turnover multiple (median over expiries)"); ax.legend(fontsize=8); fig.tight_layout()
fig.savefig(out / "fig4_expiry_profile_true.png", dpi=300); plt.close(fig)
print("figs 3,4 saved")

# Fig 5: six-index monthly turnover, NSE and BSE (log), treated vs retained-weekly ------------------
ma = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet")
ma = ma[(ma.ym >= pd.Period("2023-01")) & (ma.ym < pd.Period("2026-10")) & (ma.tot > 0)].copy(); ma["t"] = ma.ym.dt.to_timestamp()
fig, ax = plt.subplots(figsize=(8, 4.5))
sty = {"NIFTY": ("#1f77b4", "-"), "SENSEX": ("#17becf", "-"), "BANKNIFTY": ("#d62728", "--"), "FINNIFTY": ("#ff7f0e", "--"), "MIDCPNIFTY": ("#2ca02c", "--"), "BANKEX": ("#9467bd", "--")}
for s_, g in ma.groupby("Symbol"):
    ax.plot(g.t, g.tot, color=sty[s_][0], ls=sty[s_][1], label=s_ + (" (kept weekly)" if s_ in ("NIFTY", "SENSEX") else " (weekly retired)"))
ax.axvline(cut, ls=":", c="k"); ax.set_yscale("log"); ax.set_ylabel("Monthly F&O turnover (INR, log)"); ax.legend(fontsize=7, ncol=2)
ax.set_title("Weekly contract retired vs kept: NSE and BSE"); fig.tight_layout(); fig.savefig(out / "fig5_six_index_turnover.png", dpi=300); plt.close(fig)
print("fig5 saved")

# Fig 6: timing + placebo (indexed to 2024-09 = 100): treated vs retained-weekly vs never-weekly stock F&O -------------
st = pd.read_parquet(config.INTERIM_DATA_DIR / "stock_fo_daily.parquet"); st["ym"] = st.Date.dt.to_period("M")
stm = st.groupby("ym")[["Value_StockOpt", "Value_StockFut"]].sum().sum(axis=1)
pm = pd.read_parquet(config.INTERIM_DATA_DIR / "monthly_expiry_panel_all.parquet").pivot(index="ym", columns="Symbol", values="tot")
pm["STOCK F&O (never weekly)"] = stm
w = pm.loc["2024-03":"2025-09", ["BANKNIFTY", "FINNIFTY", "BANKEX", "NIFTY", "SENSEX", "STOCK F&O (never weekly)"]]
w = w / w.loc["2024-09"] * 100
fig, ax = plt.subplots(figsize=(8, 4.5))
for c_ in w.columns:
    ax.plot(w.index.to_timestamp(), w[c_], label=c_, ls="--" if c_ in ("BANKNIFTY", "FINNIFTY", "BANKEX") else "-", lw=2.5 if "STOCK" in c_ else 1.5)
ax.axvline(cut, c="k", ls=":"); ax.axvline(pd.Timestamp("2025-02-01"), c="grey", ls=":"); ax.set_yscale("log")
ax.set_ylabel("Monthly turnover, Sep 2024 = 100 (log)"); ax.legend(fontsize=7); ax.set_title("Timing: drop coincides with the Nov-2024 weekly retirement")
fig.tight_layout(); fig.savefig(out / "fig6_timing_and_stock_placebo.png", dpi=300); plt.close(fig); print("fig6 saved")
