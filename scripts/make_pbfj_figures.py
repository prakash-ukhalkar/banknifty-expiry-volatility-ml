"""LEGACY (wrong-calendar inputs; superseded by scripts/make_corrected_figures.py).

Generates the figures needed for the PBFJ manuscript's primary (diff-in-diff
liquidity-concentration) and secondary (honest-null predictability/regime)
results sections, from the JSON results already produced by:
  - scripts/event_study_leads_lags.py
  - scripts/expiry_volume_oi_event_study.py
  - scripts/walk_forward_backtest.py
  - scripts/regime_shift_event_study.py (not separately plotted; summarized in text)

Output: results/figures/*.png at 300 dpi (Elsevier photograph/chart minimum).
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import config

FIG_DIR = config.FIGURES_DIR


def load(path):
    with open(path) as f:
        return json.load(f)


def fig_event_study_leads_lags():
    d = load(config.RESULTS_DIR / "event_study_leads_lags.json")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    for ax, (metric, title) in zip(
        axes,
        [("Total_Value", "(a) Turnover (log points)"), ("Total_OpenInterest_Notional", "(b) Open interest (log points)")],
    ):
        rows = sorted(d[metric], key=lambda r: int(r["period_half_years_from_event"]))
        x = [int(r["period_half_years_from_event"]) for r in rows]
        y = [r["coef"] for r in rows]
        lo = [r["coef"] - r["ci_lower"] for r in rows]
        hi = [r["ci_upper"] - r["coef"] for r in rows]
        colors = ["#4477AA" if p < 0 else "#CC6677" for p in x]
        ax.errorbar(x, y, yerr=[lo, hi], fmt="o", color="black", ecolor="gray",
                     elinewidth=1, capsize=3, markersize=5, zorder=3)
        ax.scatter(x, y, c=colors, zorder=4, s=40)
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.axvline(-0.5, color="#CC6677", linewidth=1.2, linestyle=":")
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Half-years relative to Nov 2024 weekly-options discontinuation")
        ax.set_ylabel("Expiry x Bank Nifty coefficient")
        ax.grid(alpha=0.25)

    fig.suptitle("Event-study coefficients: Bank Nifty expiry-day effect relative to Nifty 50, by half-year period", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = FIG_DIR / "event_study_leads_lags.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved {out}")


def fig_expiry_volume_profile():
    d = load(config.RESULTS_DIR / "expiry_volume_oi_event_study.json")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, (key, title, ylabel) in zip(
        axes,
        [("event_window_Total_Volume", "(a) Contract volume around expiry day", "Mean daily volume (contracts)"),
         ("event_window_Total_OpenInterest", "(b) Open interest around expiry day", "Mean daily open interest (contracts)")],
    ):
        profile = d[key]
        offsets = sorted(int(k) for k in profile.keys())
        means = [profile[str(o)]["mean"] for o in offsets]
        colors = ["#CC6677" if o == 0 else "#4477AA" for o in offsets]
        ax.bar([str(o) for o in offsets], means, color=colors)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Trading days relative to expiry (0 = expiry day)")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.25, axis="y")

    fig.suptitle("Bank Nifty trading activity in the expiry-day event window (pooled, full sample)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = FIG_DIR / "expiry_volume_profile.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved {out}")


def fig_walk_forward_directional_accuracy():
    d = load(config.RESULTS_DIR / "walk_forward_results.json")
    pooled = d["pooled_significance"]

    conditions = ["Baseline (Technical Only)", "Baseline + Expiry", "Baseline + Regime", "Proposed (Combined)"]
    means, lo, hi = [], [], []
    for c in conditions:
        ci = pooled[f"DirAcc_CI_{c}"]
        means.append(ci["accuracy_mean"] * 100)
        lo.append((ci["accuracy_mean"] - ci["ci_2.5"]) * 100)
        hi.append((ci["ci_97.5"] - ci["accuracy_mean"]) * 100)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(conditions))
    ax.bar(x, means, yerr=[lo, hi], capsize=4, color="#4477AA", alpha=0.85)
    ax.axhline(50, color="black", linewidth=1, linestyle="--", label="Chance (50%)")
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace(" (Technical Only)", "\n(Technical)").replace(" (Combined)", "\n(Combined)").replace("Baseline + ", "Baseline +\n") for c in conditions], fontsize=9)
    ax.set_ylabel("Pooled out-of-fold directional accuracy (%)")
    ax.set_title("Walk-forward directional accuracy with 95% bootstrap CIs\n(next-day return prediction, all conditions)")
    ax.set_ylim(35, 60)
    ax.legend()
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    out = FIG_DIR / "walk_forward_directional_accuracy.png"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved {out}")


if __name__ == "__main__":
    fig_event_study_leads_lags()
    fig_expiry_volume_profile()
    fig_walk_forward_directional_accuracy()
