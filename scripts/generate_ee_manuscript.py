"""
Builds the Empirical Economics submission files (Word) from the saved result files, so that every number in the text and tables
traces to results/*.json or data/interim/*.parquet.  Output folder: manuscript/empirical-economics-files/
  Manuscript.docx (single-blind, decimal headings, Declarations before References), Title_Page.docx, Cover_Letter.docx,
  Online_Resource_1.docx (supplementary tables), plus figures/ (made by scripts/make_ee_figures.py).
Run:  python -m scripts.generate_ee_manuscript
"""
import json
from pathlib import Path
import numpy as np, pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm

from src import config

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "manuscript" / "empirical-economics-files"; FIG = OUT / "figures"
R = config.RESULTS_DIR; I = config.INTERIM_DATA_DIR
J = lambda n: json.load(open(R / n))

csn = J("calendar_sensitivity.json")
xd, rb, om, mq, pt, its, cl = (J("cross_exchange_did.json"), J("corrected_robustness.json"), J("option_microstructure_did.json"),
                               J("market_quality_did.json"), J("pretrend_sensitivity.json"), J("its_clean_contrasts.json"),
                               J("regime_shift_event_study_true_calendar.json"))
wf = J("walk_forward_results_true_calendar.json")["pooled_significance"]
NSE, BSE = xd["NSE: BANKNIFTY vs NIFTY"], xd["BSE: BANKEX vs SENSEX"]
PW, SUB, PART = xd["pooled_twfe"], xd["substitution"], xd["participants"]
AUD = rb["calendar_audit"]; PLA = rb["in_time_placebo"]; DOSE = om["dose_response"]; STK = om["stock_placebo"]
PN, PB = pt["NSE: BANKNIFTY vs NIFTY"], pt["BSE: BANKEX vs SENSEX"]
MQN, MQB = mq["NSE: BANKNIFTY vs NIFTY"], mq["BSE: BANKEX vs SENSEX"]

f2 = lambda v: f"{v:.2f}"; f3 = lambda v: f"{v:.3f}"; pc = lambda v: f"{100 * v:.0f}%"
def pv(p): return "<0.001" if p < 0.001 else f"{p:.3f}"
def eff(x): return f"{100 * (np.exp(x) - 1):+.0f}%"

# ---------------------------------------------------------------- descriptives
m = pd.read_parquet(I / "monthly_expiry_panel_all.parquet")
pre = m[(m.ym >= pd.Period("2024-01")) & (m.ym <= pd.Period("2024-09")) & (m.exp_day > 0)]
post = m[(m.ym >= pd.Period("2025-01")) & (m.ym <= pd.Period("2026-09")) & (m.exp_day > 0)]
ORDER = ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "BANKEX", "NIFTY", "SENSEX"]
D = {s: {"pre": pre[pre.Symbol == s], "post": post[post.Symbol == s]} for s in ORDER}
panel = pd.read_parquet(I / "index_expiry_panel.parquet")
nexp = panel[(panel.Symbol == "BANKNIFTY")].set_index("Date").NExpiriesListed
n_before, n_after = int(nexp.loc["2024-10-16"]), int(nexp.loc["2024-11-14"])
ncontracts = len(pd.read_parquet(I / "options_contracts.parquet", columns=["Symbol"]))
ndays = panel[panel.Symbol == "NIFTY"].Date.nunique()
od = om["descriptives"]

# ---------------------------------------------------------------- docx helpers
doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
for s_ in doc.sections: s_.left_margin = s_.right_margin = Cm(2.5); s_.top_margin = s_.bottom_margin = Cm(2.5)
sec = doc.sections[0]
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = fp.add_run()
for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
    if tag:
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tag)
    else:
        e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = text
    run._r.append(e)


def H(text, lvl=1):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = True; r.font.size = Pt({1: 13, 2: 11.5, 3: 11}[lvl]); r.italic = lvl == 3
    p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(4); p.paragraph_format.keep_with_next = True
    return p


def P(text, italic=False, indent=False, after=6):
    p = doc.add_paragraph(); r = p.add_run(text); r.italic = italic
    p.paragraph_format.space_after = Pt(after); p.paragraph_format.line_spacing = 1.3
    if indent: p.paragraph_format.left_indent = Cm(1)
    return p


def EQ(text):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = p.add_run(text); r.italic = True
    p.paragraph_format.space_after = Pt(6); return p


def CAP(label, text):
    p = doc.add_paragraph(); r = p.add_run(label); r.bold = True; p.add_run(" " + text); p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = label.startswith("Table"); return p


def TABLE(rows, header, widths=None, note=None, fs=8.5):
    t = doc.add_table(rows=1, cols=len(header)); t.style = "Table Grid"
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ""; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(fs)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(fs)
            if i > 0: cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if note:
        p = doc.add_paragraph(); r = p.add_run(note); r.font.size = Pt(8.5); p.paragraph_format.space_after = Pt(8)
    return t


def FIGURE(name, caption, width=15.5):
    doc.add_picture(str(FIG / f"{name}.png"), width=Cm(width)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    CAP(f"Fig. {name[3:]}", caption)


# ---------------------------------------------------------------- title + abstract
TITLE = "Collapse, concentration and migration: evidence from the retirement of weekly index options in India"
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = p.add_run(TITLE); r.bold = True; r.font.size = Pt(15)
H("Abstract", 1)
CS_T, CS_O = csn["true_expiry_dates"], csn["rule_based_calendar"]
DR_T, DR_O = csn["daily_ratio_of_ratios"]["true_expiry_dates"]["coef"], csn["daily_ratio_of_ratios"]["rule_based_calendar"]["coef"]
ABSTRACT = (
    f"A regulatory rule limited each Indian exchange to one weekly index-options expiry. The National Stock Exchange (NSE) retired weekly options on "
    f"Bank Nifty, Fin Nifty and Midcap Nifty and BSE retired them on Bankex, while Nifty 50 and Sensex kept theirs. We reconstruct expiry dates from "
    f"exchange records. A rule-based calendar misclassifies {AUD['BANKNIFTY']['mismatched_since_2024-11-14']} of 23 post-reform Bank Nifty monthly expiries and changes the sign of the expiry-day share effect, "
    f"from {CS_T['ls']['coef']:+.1f} to {CS_O['ls']['coef']:+.1f} log points. Relative to the retained-weekly index on the same exchange, turnover on the retired index fell by {abs(NSE['lt']['coef']):.1f} log points "
    f"on NSE and {abs(BSE['lt']['coef']):.1f} on BSE, while the expiry-day share of monthly turnover rose by {NSE['ls']['coef']:.1f} and {BSE['ls']['coef']:.1f}. "
    f"Expiry-day turnover in levels did not rise, so trading did not re-time onto the surviving monthly expiry, even though a regression of expiry-day on other-day turnover suggests a large rise. A never-weekly placebo (stock derivatives) "
    f"fell {100 * (1 - STK['stock_fo_post_over_pre']):.0f}%, and a daily dose-response ties the Bank Nifty decline to each weekly series as it was withdrawn. With six units we use exact randomization "
    f"inference, whose smallest attainable p-value is {1 / 15:.3f}, and a smoothness-based pre-trend sensitivity analysis: the share and turnover results survive "
    f"post-period curvature of {PN['ls']['breakdown_multiple_of_M_pre']:.1f} and {PN['lt']['breakdown_multiple_of_M_pre']:.1f} times the largest pre-period curvature, whereas the expiry-day level result does not. "
    f"Migration to the surviving weeklies is large but not point-identified.")
P(ABSTRACT)
wc = len(ABSTRACT.split())
P("Keywords: weekly options; derivatives regulation; policy evaluation; difference-in-differences; expiry-day concentration; India", after=2)
P("JEL classification: G18, G13, C23, G15", after=8)

# ---------------------------------------------------------------- 1 Introduction
H("1 Introduction")
P("Retail participation in short-dated index options has grown rapidly in several markets (Bryzgalova et al. 2023), and regulators now ask whether limiting weekly contracts reduces speculative "
  "trading or merely relocates it. India is a prominent case. In October 2024 the Securities and Exchange Board of India (SEBI) restricted each exchange to a "
  "single weekly index-options expiry (SEBI 2024a). A SEBI study published shortly before reported that most individual traders in the equity derivatives segment lost money, "
  "with losses concentrated in weekly index options (SEBI 2024b). NSE kept weekly options on Nifty 50 and discontinued them on Bank Nifty, Fin Nifty and Midcap Nifty; BSE kept "
  "them on Sensex and discontinued them on Bankex.")
P("This paper measures what the retirement did to trading activity, and it makes two measurement points that change the answer. First, a calendar of expiry dates built from the exchange's announced weekday rules "
  f"misclassifies {AUD['BANKNIFTY']['mismatched_since_2024-11-14']} of 23 post-reform Bank Nifty monthly expiries and {AUD['NIFTY']['mismatched_since_2024-11-14']} of 23 for Nifty; in our design it turns an expiry-day share increase of "
  f"{CS_T['ls']['coef']:+.2f} log points into {CS_O['ls']['coef']:+.2f}. Second, comparing expiry-day with other-day turnover is a ratio of ratios: it gives a large positive triple-interaction estimate ({DR_T:+.2f} with true dates) even though the "
  "level of expiry-day turnover fell, because other-day turnover collapsed. Rebuilt from exchange records and decomposed into levels and shares, the evidence is clear. "
  "Total turnover on the retired indices collapsed, the expiry day became a much larger share of what remained, and the level of expiry-day turnover fell. Activity "
  "did not re-time onto the surviving monthly expiry; it disappeared from the retired contracts and, in large part, appeared on the retained weeklies.")
P("We make three contributions. First, a measurement contribution: a reproducible procedure for deriving expiry dates from contract-level exchange files, an audit of "
  "rule-based calendars, and a decomposition of expiry-day concentration into level and share effects. Second, a design contribution: two exchanges that each retired one "
  "weekly contract and kept another, a never-weekly placebo group, a daily dose-response during the phase-out, and inference suited to six units (exact randomization "
  "over treatment assignments) together with a smoothness-based sensitivity analysis for pre-trends in the spirit of Rambachan and Roth (2023). Third, a short conceptual "
  "framework with five testable predictions, which maps each empirical result to a behavioural margin: collapse of weekly-linked speculation, concentration through "
  "inelastic hedging and rollover, and the absence of re-timing.")
P("The paper is related to the expiration-day literature (Stoll and Whaley 1987; Ni et al. 2005; Golez and Jackwerth 2012) and to Indian evidence (Vipul 2005; Narang and Vij "
  "2013; Agarwalla and Pandey 2013), which documents volume effects of settlement but studies fixed expiry cycles. It is related to work on short-dated options and "
  "retail participation (Andersen et al. 2017; Bryzgalova et al. 2023; Barber et al. 2022), and to the econometrics of policy evaluation with few treated units "
  "(Bertrand et al. 2004; Conley and Taber 2011; Abadie et al. 2010; Callaway and Sant'Anna 2021). We do not observe accounts, order books or option spreads, so we make no welfare "
  "claims; our contribution is a credible description of how the activity moved.")
P("Section 2 describes the institutional setting. Section 3 sets out the conceptual framework. Section 4 describes the data and measurement. Section 5 presents the empirical "
  "strategy, Section 6 the results, Section 7 discusses implications and limitations, and Section 8 concludes.")

# ---------------------------------------------------------------- 2 Institutional background
H("2 Institutional background")
H("2.1 The single-weekly-expiry rule", 2)
P("Before the rule, NSE listed weekly options on Nifty 50, Bank Nifty, Fin Nifty and Midcap Nifty, and BSE listed weekly options on Sensex and Bankex. Weekly options expire "
  "at the end of a weekly cycle; the contract that expires last in a month is the monthly contract, and its expiry coincides with a weekly expiry day. SEBI's October 2024 "
  "circular limited each exchange to one weekly index-options expiry per week (SEBI 2024a) and was accompanied by changes to contract size and to expiry-day margining and "
  "position monitoring that were phased in over the following months. Those other measures applied to all indices, which is why we use retained-weekly indices on the same exchange "
  "as controls and examine timing explicitly.")
P(f"The exchange files record the phase-out directly. On NSE the number of distinct Bank Nifty option expiries listed fell from {n_before} on 16 October 2024 to {n_after} on 14 November 2024 "
  "as weekly series stopped being renewed; the last Bank Nifty weekly expiry traded on 13 November 2024 and every later expiry is monthly. We therefore set the cutover at 14 November 2024 "
  "and treat November 2024 as a transition month that is excluded from all estimates.")
H("2.2 Why expiry dates must be measured, not assumed", 2)
P("Exchanges moved expiry weekdays several times, and the weekday differed across indices and contract types. Bank Nifty weeklies expired on Wednesdays from September 2023 while "
  "Nifty weeklies expired on Thursdays; after the retirement the Bank Nifty monthly expiry was the last Thursday of the month until August 2025 and the last Tuesday afterwards. A single "
  "rule-based calendar applied to both indices is therefore wrong for many dates, as Section 4.2 documents.")

# ---------------------------------------------------------------- 3 Framework
H("3 Conceptual framework and testable predictions")
P("We use a deliberately simple accounting framework to organise the predictions; it is not a full equilibrium model. Consider an index i with a monthly cycle of D trading days. "
  "Turnover on index i has two components. Hedging and rollover volume H is concentrated around settlement: a share h_e of it falls on the monthly expiry day. Weekly-linked "
  "speculative volume S is spread over the weekly cycle: a share s_e of it falls on the monthly expiry day, and the rest on other days. Retiring the weekly contract removes "
  "the fraction 1 − ρ of S; a fraction μ of the removed volume migrates to the retained weekly on another index, a fraction φ is re-timed onto the surviving monthly expiry "
  "day, and the remainder exits.")
EQ("T = H + S,     E = h_e H + s_e S,     share = E / T")
P("Hypothesis H1 (collapse). Total turnover on the retired index falls by (1 − ρ)S, so it falls whenever weekly-linked speculation is non-trivial. H2 (concentration). "
  "After retirement the expiry-day share is (h_e H + ρ s_e S)/(H + ρ S) plus any re-timed volume; absent re-timing it rises if and only if h_e > s_e, that is, if hedging and rollover "
  "volume is more concentrated on the monthly expiry day than speculative volume. Because settlement-driven demand is tied to the expiry date while speculative demand is spread "
  "across the cycle, we expect h_e > s_e. H3 (re-timing). Let φ be the fraction of the removed off-expiry-day speculative volume that is re-timed onto the monthly expiry day. Then E changes by −(1 − ρ)s_e S + φ(1 − ρ)(1 − s_e)S, which is positive if and only if φ(1 − s_e) > s_e. A fall in E therefore indicates little re-timing, and the size "
  "of the fall measures how much of the expiry-day volume was weekly-linked. H4 (migration). Turnover on the retained-weekly index rises by μ(1 − ρ)S_i, so six-index turnover "
  "falls by (1 − μ)(1 − ρ)S_i; μ is bounded by [0,1] but is not identified from levels alone because the retained indices also had their own growth. H5 (placebo and dose). Products that never had "
  "weeklies are unaffected, and the effect on a retired index scales with the number of weekly series removed. Thick-market externalities (Pagano 1989; Admati and Pfleiderer 1988) "
  "are the natural reason that μ would favour the most liquid surviving weekly.")

# ---------------------------------------------------------------- 4 Data
H("4 Data and measurement")
H("4.1 Data sources", 2)
P(f"We use NSE's daily futures-and-options Bhavcopy for {ndays:,} trading days from January 2020 to October 2026, in both the legacy format (before 8 July 2024) and the UDiFF format (from 8 July 2024), "
  "and BSE's daily derivatives market summary for the same days. Both report, for every traded contract, expiry date, strike, option type, prices, volume, traded value and open interest. "
  "Traded value is notional value in rupees, which does not depend on the lot size. NSE's participant-wise volume files are used for the investor mix. "
  f"From these files we build (i) a contract-level index-options panel of {ncontracts / 1e6:.1f} million contract-days for six indices (Nifty 50, Bank Nifty, Fin Nifty, Midcap Nifty, Sensex, Bankex), "
  "(ii) a near-month index-futures daily series, and (iii) a daily aggregate of stock futures and options, which never had weekly contracts and serves as a placebo group. "
  "The raw files are public; our processed panels and code are described in the Declarations.")
H("4.2 True expiry dates and an audit of rule-based calendars", 2)
P("A day is an expiry day for an index if option contracts with that expiry traded on that day. The monthly expiry is the last such day in each calendar month. "
  "We compare this with a calendar built from the exchange's announced weekday rules (last Thursday, then last Wednesday, then last Tuesday, with holiday roll-back) applied to both indices.")
TABLE([[s, AUD[s]["true_monthly_expiries"], AUD[s]["matched_by_old_calendar"], AUD[s]["mismatched"], AUD[s]["mismatched_since_2024-11-14"]] for s in ["BANKNIFTY", "NIFTY"]],
      ["Index", "True monthly expiries", "Matched by rule-based calendar", "Mismatched", "Mismatched since 14 Nov 2024"])
CAP("Table 1", "Audit of a rule-based expiry calendar against expiry dates derived from contract-level exchange files, January 2020 to October 2026. Source: authors' calculations from NSE Bhavcopy files.")
P("Table 1 reports the audit. Misclassification is concentrated after the retirement, when the monthly expiry was the last Thursday but the rule-based calendar flagged the preceding Wednesday or Tuesday. "
  "Because the misclassified days are precisely the treated expiries, the error is correlated with treatment. Table 2 shows how much it matters in the monthly design of Section 5.1.")
TABLE([["Log expiry-day turnover (level)", f"{CS_T['le']['coef']:+.2f} ({CS_T['le']['se']:.2f})", f"{CS_O['le']['coef']:+.2f} ({CS_O['le']['se']:.2f})"],
       ["Log expiry-day share", f"{CS_T['ls']['coef']:+.2f} ({CS_T['ls']['se']:.2f})", f"{CS_O['ls']['coef']:+.2f} ({CS_O['ls']['se']:.2f})"],
       ["Daily expiry-day x post x Bank Nifty (log turnover)", f"{DR_T:+.2f}", f"{DR_O:+.2f}"]],
      ["Estimate (Bank Nifty vs Nifty)", "Expiry dates from exchange files", "Rule-based calendar"])
CAP("Table 2", "Sensitivity of the Bank Nifty versus Nifty difference-in-differences to the expiry calendar (log points; standard errors clustered by month in parentheses). The last row is the daily triple interaction of an expiry-day indicator, the post period and Bank Nifty, with weekday effects, a trend and Newey-West errors. Sample June 2023 to September 2026, November 2024 excluded.")
H("4.3 Outcomes", 2)
P("The unit of analysis is an index-month. For each index-month we compute total turnover T (futures plus options), expiry-day turnover E (turnover on the monthly expiry day) and the "
  "expiry-day share E/T. We analyse log T, log E and log share. Using shares and levels together is essential: a regression of expiry-day versus other-day turnover is a ratio of ratios, "
  "and it can rise when expiry-day turnover is unchanged and other-day turnover collapses. Months with no completed monthly expiry in the data (October 2026) are dropped.")
H("4.4 Sample", 2)
P("Table 3 and Fig. 1 describe the data. The estimation window is June 2023 to September 2026, with November 2024 dropped. Bankex and Midcap Nifty were illiquid new products during part of the pre-period, so their "
  "pre-reform paths are noisy; we report results for the pairs separately and treat pooled results with caution.")
TABLE([[{"BANKNIFTY": "Bank Nifty", "FINNIFTY": "Fin Nifty", "MIDCPNIFTY": "Midcap Nifty", "BANKEX": "Bankex", "NIFTY": "Nifty", "SENSEX": "Sensex"}[s],
        f"{D[s]['pre'].tot.mean() / 1e12:,.0f}", f"{D[s]['post'].tot.mean() / 1e12:,.0f}",
        f"{D[s]['pre'].exp_day.mean() / 1e12:,.0f}", f"{D[s]['post'].exp_day.mean() / 1e12:,.0f}",
        f"{D[s]['pre'].share.mean():.2f}", f"{D[s]['post'].share.mean():.2f}",
        f"{D[s]['pre'].nexp.mean():.1f}", f"{D[s]['post'].nexp.mean():.1f}"] for s in ORDER],
      ["Index", "Monthly turnover before", "after", "Expiry-day turnover before", "after", "Share before", "after", "Expiries per month before", "after"], fs=8)
CAP("Table 3", "Monthly turnover, expiry-day turnover (INR trillion), expiry-day share and number of expiry days per month. Before = January to September 2024; after = January 2025 to September 2026. Indices in the first four rows lost their weekly contract; Nifty and Sensex kept theirs. Source: authors' calculations.")
FIGURE("Fig1", "Monthly F&O turnover (a) and expiry-day share of monthly turnover (b) for six indices. The vertical line marks 14 November 2024. Dashed and dotted lines are indices that lost their weekly contract; solid lines kept it")
H("4.5 Use of AI tools", 2)
P("A large language model (Claude, Anthropic) was used to help write and debug the analysis code, to assemble tables from saved results and to draft text. The authors specified the design, "
  "checked the derived panels against the raw exchange files (including the expiry-date audit), reviewed every number against the saved result files, and are responsible for the content. "
  "The model is not an author.")

# ---------------------------------------------------------------- 5 Strategy
H("5 Empirical strategy")
H("5.1 Difference-in-differences", 2)
P("For each exchange we compare the retired index with the retained-weekly index on the same exchange (Bank Nifty versus Nifty 50 on NSE; Bankex versus Sensex on BSE):")
EQ("y_st = α + a·Tr_s + b·Post_t + β·(Tr_s × Post_t) + g·t + h·(Tr_s × t) + ε_st")
P("where y is log T, log E or log share, Tr_s indicates the retired index, Post_t indicates December 2024 onwards, and the index-specific linear trend absorbs differential growth before the "
  "reform. Standard errors are clustered by month. A pooled specification with index and month fixed effects, y_st = α_s + γ_t + β·D_st + ε_st with D_st = 1 for retired indices after the cutover, uses "
  "all six indices. Because the retained indices were also affected, β measures a relative effect and is not a clean counterfactual; we say so wherever it matters.")
H("5.2 Inference with six units", 2)
P("Asymptotic or cluster-robust inference is unreliable with six units and two policy-affected controls (Bertrand et al. 2004; Conley and Taber 2011). We therefore also report exact "
  "randomization inference (Fisher 1935; Imbens and Rubin 2015): under the sharp null of no effect, the treatment labels of the four retired indices could have been assigned to any of the "
  "C(6,4) = 15 subsets of indices, and we compare the pooled estimate with the 15 re-assigned estimates. The smallest attainable two-sided p-value is 1/15 = 0.067, which is a property of the "
  "design, not of the evidence.")
H("5.3 Placebo, timing and dose-response", 2)
P("We use (i) in-time placebos that move the cutover to each month from July 2021 to January 2024 using pre-period data only; (ii) stock futures and options, which never had weeklies, as a "
  "never-treated group; (iii) the timing of the break relative to later measures; and (iv) a daily dose-response during the phase-out, regressing the daily log turnover gap between Bank Nifty and "
  "Nifty on the number of Bank Nifty option expiries listed, with weekday fixed effects and Newey-West errors.")
H("5.4 Pre-trend sensitivity", 2)
P("Quarterly event-study coefficients (reference quarter 2024Q3) show modest differential pre-trends. Following the smoothness restriction of Rambachan and Roth (2023), we treat the pre-period "
  "coefficients as pure differential trend and bound the post-period differential trend by requiring that its second differences do not exceed M. The identified set for the average post-period "
  "effect is obtained by linear programming. Let M_pre be the largest second difference of the estimated pre-period path; the breakdown value is the smallest multiple of M_pre at which the identified set "
  "includes zero. We report the identified set at the point estimates and do not implement the robust confidence sets of Rambachan and Roth (2023), so the analysis is a sensitivity analysis, not "
  "a confidence interval.")

# ---------------------------------------------------------------- 6 Results
H("6 Results")
H("6.1 Collapse, concentration and the level of expiry-day turnover", 2)
P("Table 4 reports the main estimates and Fig. 2 the event study.")
rows = []
for lab, d in [("NSE: Bank Nifty vs Nifty", NSE), ("BSE: Bankex vs Sensex", BSE)]:
    rows.append([lab] + [f"{d[o]['coef']:+.2f} ({d[o]['se']:.2f})" for o in ("lt", "le", "ls")] + [d["lt"]["n"]])
rows.append(["Pooled, six indices (two-way FE)"] + [f"{PW[o]['coef']:+.2f} [p_RI = {PW[o]['randomization_p_two_sided']:.3f}]" for o in ("lt", "le", "ls")] + [""])
TABLE(rows, ["Design", "Log total turnover", "Log expiry-day turnover", "Log expiry-day share", "N"])
CAP("Table 4", "Difference-in-differences estimates (log points) for the retirement of weekly options. Within-exchange rows: standard errors clustered by month in parentheses. Pooled row: coefficient on retired × post with exact randomization p-value over the 15 treatment assignments in brackets. Sample June 2023 to September 2026, November 2024 excluded.")
P(f"On NSE, turnover on Bank Nifty fell by {abs(NSE['lt']['coef']):.2f} log points relative to Nifty ({eff(NSE['lt']['coef'])}), and on BSE turnover on Bankex fell by {abs(BSE['lt']['coef']):.2f} relative to Sensex. "
  f"The expiry-day share rose by {NSE['ls']['coef']:.2f} and {BSE['ls']['coef']:.2f} log points respectively, so the expiry day became a much larger part of what remained. Expiry-day turnover in levels fell on NSE "
  f"({NSE['le']['coef']:+.2f}, p = {pv(NSE['le']['p'])}) and fell, with wide uncertainty, on BSE ({BSE['le']['coef']:+.2f}, p = {pv(BSE['le']['p'])}). This is the pattern H1–H3 predict if weekly-linked volume "
  "is large and little of it is re-timed onto the monthly expiry. In the pooled design the share effect ranks first of the 15 possible assignments "
  f"(p_RI = {PW['ls']['randomization_p_two_sided']:.3f}, the smallest value attainable), whereas the turnover and level effects do not stand out from re-assignments "
  f"(p_RI = {PW['lt']['randomization_p_two_sided']:.2f} and {PW['le']['randomization_p_two_sided']:.2f}), which may reflect heterogeneity across the four retired indices.")
FIGURE("Fig2", "Event-study coefficients for Bank Nifty relative to Nifty: log total turnover (a) and log expiry-day share (b), by quarter relative to 2024Q4 (reference 2024Q3). Bars are 95% confidence intervals with heteroskedasticity-robust standard errors. The vertical line marks the retirement of the weekly contract")
FIGURE("Fig3", "Median turnover multiple around the monthly expiry day (day 0), relative to the median of the prior month's ordinary days, for Bank Nifty and Nifty before (January 2023 to September 2024) and after (January 2025 to September 2026) the reform", width=11)
P("Fig. 3 shows that, relative to its own ordinary days, Bank Nifty's expiry day became much larger after the reform, from a multiple of about four to about twenty, while Nifty's stayed at three to four. "
  "This is concentration relative to a shrunken base, not a rise in the level of expiry-day turnover.")
H("6.2 Placebo, timing and dose-response", 2)
P(f"Fig. 4 compares the paths. Stock futures and options, which never had weeklies, changed little: post-period monthly turnover was {STK['stock_fo_post_over_pre']:.2f} times its pre-period level. "
  f"The retired indices were at {STK['BANKNIFTY_post_over_pre']:.2f} (Bank Nifty), {STK['FINNIFTY_post_over_pre']:.2f} (Fin Nifty), {STK['MIDCPNIFTY_post_over_pre']:.2f} (Midcap Nifty) and {STK['BANKEX_post_over_pre']:.2f} (Bankex), "
  f"and the retained-weekly indices at {STK['NIFTY_post_over_pre']:.2f} (Nifty) and {STK['SENSEX_post_over_pre']:.2f} (Sensex). The collapse is therefore not a market-wide shock to derivatives. "
  f"The in-time placebos produce effects between {min(v['placebo_min'] for v in PLA.values() if isinstance(v, dict) and 'placebo_min' in v):+.2f} and {max(v['placebo_max'] for v in PLA.values() if isinstance(v, dict) and 'placebo_max' in v):+.2f} log points, against "
  f"{PLA['lt']['true']:+.2f} (turnover), {PLA['le']['true']:+.2f} (expiry-day level) and {PLA['ls']['true']:+.2f} (share) at the true date (none of the {PLA['lt']['n_placebos']} overlapping placebo effects is as large in absolute value; this is informal because the placebos are not independent). "
  f"The daily dose-response gives a log turnover gap between Bank Nifty and Nifty that rises by {DOSE['coef_per_listed_expiry']:.2f} (s.e. {DOSE['se']:.2f}, N = {DOSE['n']}) per Bank Nifty option expiry listed, "
  "consistent with H5 and with the decline following the phase-out rather than later measures.")
FIGURE("Fig4", "Monthly turnover indexed to September 2024 = 100 (log scale) for retired indices (dashed and dotted), retained-weekly indices (solid) and aggregate stock futures and options (thick line). The vertical line marks 14 November 2024")
H("6.3 Pre-trend sensitivity", 2)
P("Table 5 and Fig. 5 report the sensitivity analysis.")
def prow(lab, y):
    r = PN[y]; b = r["bounds"]
    return [lab, f"{r['theta_naive']:+.2f}", f"[{b['0xM_pre'][0]:+.2f}, {b['0xM_pre'][1]:+.2f}]", f"[{b['0.5xM_pre'][0]:+.2f}, {b['0.5xM_pre'][1]:+.2f}]",
            f"[{b['1xM_pre'][0]:+.2f}, {b['1xM_pre'][1]:+.2f}]", f"{r['breakdown_multiple_of_M_pre']:.2f}"]
TABLE([prow("Log expiry-day share", "ls"), prow("Log total turnover", "lt"), prow("Log expiry-day turnover", "le")],
      ["Outcome (Bank Nifty vs Nifty)", "Event-study average", "M = 0", "M = 0.5 M_pre", "M = 1 M_pre", "Breakdown (× M_pre)"])
CAP("Table 5", "Smoothness-based pre-trend sensitivity for the average post-period effect: identified sets (log points) for the bound M on second differences of the differential trend, in multiples of the largest pre-period second difference M_pre, at the point estimates (sampling error ignored). The breakdown value is the smallest multiple of M_pre at which zero enters the set.")
P(f"With M = 0 the differential trend is extrapolated linearly and the share effect is {PN['ls']['bounds']['0xM_pre'][0]:+.2f}. The share and turnover effects exclude zero for post-period curvature up to "
  f"{PN['ls']['breakdown_multiple_of_M_pre']:.2f} and {PN['lt']['breakdown_multiple_of_M_pre']:.2f} times the largest pre-period curvature, so they are not robust to a trend break as rough as the roughest pre-period wiggle; "
  f"the expiry-day level effect is more fragile ({PN['le']['breakdown_multiple_of_M_pre']:.2f}). For Bankex versus Sensex the pre-period is short and extremely noisy (M_pre = {PB['ls']['M_pre']:.1f} for the share), so the bounds are uninformative "
  "and we do not interpret them. Fig. 5 plots the identified sets.")
FIGURE("Fig5", "Identified set for the average post-period effect of the retirement on the expiry-day share (a) and on total turnover (b), as a function of the smoothness bound M in multiples of the largest pre-period second difference M_pre. The dashed line is the event-study average and the dotted line is zero", width=15)
H("6.4 Migration", 2)
sg = SUB["substitution_share_by_assumed_organic_growth"]
P(f"Six-index turnover changed by {SUB['total_6index_change_pct_naive']:+.1f}% between the pre- and post-periods, and Nifty and Sensex together gained {pc(SUB['substitution_share_naive'])} of the monthly turnover lost on the four retired indices "
  f"(Sensex INR {SUB['sensex_gain_naive'] / 1e12:,.0f} trillion, Nifty INR {SUB['nifty_gain_naive'] / 1e12:,.0f} trillion per month). Both retained indices were growing quickly before the reform "
  f"(Nifty's turnover grew {rb['nifty_yoy_growth_2023_vs_2022_pct']:.0f}% from 2022 to 2023), so some of the gain would have occurred anyway. If the retained indices would have grown at 0%, 25% or 50% a year, the migrated share "
  f"is {pc(sg['organic_growth_0pct_per_year'])}, {pc(sg['organic_growth_25pct_per_year'])} or {pc(sg['organic_growth_50pct_per_year'])} (H4). We therefore report migration as a range: it is large, but it is not point-identified from public turnover data.")
H("6.5 Contract composition and the investor mix", 2)
P("Table 6 reports the composition of option turnover.")
def orow(s, lab):
    return [lab, f"{od[s]['pre']['dte07_share']:.2f}", f"{od[s]['post']['dte07_share']:.2f}", f"{od[s]['pre']['otm5_share']:.3f}", f"{od[s]['post']['otm5_share']:.3f}"]
TABLE([orow("BANKNIFTY", "Bank Nifty"), orow("NIFTY", "Nifty"), orow("BANKEX", "Bankex"), orow("SENSEX", "Sensex")],
      ["Index", "Share ≤ 7 days to expiry, before", "after", "Share > 5% out of the money, before", "after"])
CAP("Table 6", "Composition of index-option turnover: share of turnover in contracts within seven days of expiry and in options more than 5% out of the money. Before = January to September 2024; after = January 2025 to September 2026. Source: authors' calculations from contract-level files.")
P(f"Before the reform nearly all index-option turnover on every index was within seven days of expiry. After the retirement Bank Nifty's share fell to {od['BANKNIFTY']['post']['dte07_share']:.2f} while Nifty's stayed at {od['NIFTY']['post']['dte07_share']:.2f}, "
  "which is what H1 implies if the weekly-linked volume was concentrated in short-dated contracts. The share of far out-of-the-money options rose for Bank Nifty and Nifty and fell for Bankex, so we draw no conclusion about speculative intensity from it. "
  f"On NSE as a whole, the client share of index-options volume moved from {PART['pre (2024-01..09)']['Client']:.3f} to {PART['post (2025-01..2026-09)']['Client']:.3f} and the proprietary share from "
  f"{PART['pre (2024-01..09)']['Pro']:.3f} to {PART['post (2025-01..2026-09)']['Pro']:.3f}; these market-wide shares cannot be attributed to the reform.")
H("6.6 Futures market quality", 2)
P(f"Spillovers to the liquid hedging instrument are small. For Bank Nifty versus Nifty near-month futures, the Amihud (2002) price-impact measure changed by {MQN['l_amihud']['coef']:+.3f} log points (p = {pv(MQN['l_amihud']['p'])}), "
  f"the Corwin and Schultz (2012) high-low spread by {MQN['cs_spread']['coef']:+.4f} (p = {pv(MQN['cs_spread']['p'])}) and the daily high-low range by {MQN['l_hl']['coef']:+.3f} log points (p = {pv(MQN['l_hl']['p'])}). "
  f"For Bankex versus Sensex futures the corresponding estimates are {MQB['l_amihud']['coef']:+.2f} (p = {pv(MQB['l_amihud']['p'])}), {MQB['cs_spread']['coef']:+.4f} (p = {pv(MQB['cs_spread']['p'])}) and {MQB['l_hl']['coef']:+.2f} (p = {pv(MQB['l_hl']['p'])}). "
  "These are futures proxies, not option spreads, which are not available in public files; high-low spread estimators applied to option prices mostly reflect volatility and price level, and we do not use them as market-quality evidence.")
H("6.7 Settlement-weekday reforms (Online Resource 1)", 2)
a = its["A_weekday_within_weekly_era"]; b = its["B_weekday_within_monthly_only_era"]
ps = [v["p"] for k in (a, b) for kk, v in k.items() if kk != "n"]
P(f"Settlement weekdays also changed, and weekday and weekly-contract status changed together after November 2024. Using true expiry dates, interrupted-time-series regressions across four regimes find no significant expiry-week interaction for returns or volatility "
  f"(Online Resource 1). Two clean weekday-only contrasts (Thursday to Wednesday in the weekly era; Thursday to Tuesday in the monthly-only era) give p-values between {min(ps):.3f} and {max(ps):.2f} across six tests; the smallest "
  f"({min(ps):.3f}) does not survive a correction for six tests. A five-fold walk-forward evaluation over {wf['Binomial_vs_50pct_Baseline (Technical Only)']['n_total']} out-of-fold days finds directional accuracy of 49 to 52 per cent with "
  f"Holm-adjusted p-values of at least {min(wf['Holm_Bonferroni_adjusted'].values()):.2f}.")

# ---------------------------------------------------------------- 7 Discussion
H("7 Discussion and limitations")
H("7.1 What the evidence says", 2)
P("Retiring the weekly contract did not move trading onto the monthly expiry. It removed most turnover on the retired indices, made the surviving expiry day a larger share of a much smaller base, "
  "and was accompanied by large gains on the retained weeklies. If the policy aim was to reduce speculative volume, the evidence suggests that a large part of it was displaced across underlyings (and, on BSE, to Sensex) rather than eliminated, although the migrated share is only bounded between "
  f"{pc(sg['organic_growth_50pct_per_year'])} and {pc(sg['organic_growth_0pct_per_year'])}; if the aim was to shift volume across expiry days, it did not work. The rise in expiry-day share that a naive reading would call "
  "concentration is mainly the loss of weekly-linked volume on ordinary days.")
H("7.2 Limitations", 2)
P("The evidence rests on one policy event and six indices. Exact randomization inference has a smallest attainable p-value of 0.067, the pre-trends are modest but not zero, and the pre-trend sensitivity "
  "analysis is at the point estimates without robust confidence sets. The retained indices were affected by the policy, so the difference-in-differences estimates are relative effects, and migration is not "
  "point-identified. Bankex and Midcap Nifty were thin markets with unstable pre-period paths. Other measures phased in after the rule apply to all indices; the timing evidence and the stock placebo reduce "
  "but cannot eliminate this concern. We observe neither accounts, order books nor option spreads, so we cannot say whether market quality or investor outcomes improved or deteriorated. Finally, "
  "our institutional description relies on the cited regulatory documents and on the exchange files.")

# ---------------------------------------------------------------- 8 Conclusion
H("8 Conclusion")
P("The retirement of weekly index options in India collapsed turnover on the retired indices, raised the expiry-day share of what remained and did not raise expiry-day turnover. A rule-based expiry "
  "calendar would have reversed that conclusion, which makes expiry-date measurement a first-order issue for event studies in derivatives markets. Inference is limited by six units, and the "
  "migration of activity to the retained weeklies is large but only bounded. The natural next steps are order-book and account-level data to measure market quality and investor outcomes, and further policy "
  "events with independent identification.")

# ---------------------------------------------------------------- Declarations
H("Declarations")
P("Funding: The authors did not receive support from any organization for the submitted work.", after=2)
P("Competing interests: The authors have no relevant financial or non-financial interests to disclose.", after=2)
P("Ethics approval and consent: Not applicable. The study uses public market data and no human participants.", after=2)
P("Use of AI tools: See Section 4.5.", after=2)
P("Data and computer code availability: The raw data are public (NSE futures-and-options Bhavcopy, BSE derivatives market summary and NSE participant-wise files). Code, derived panels, result files and a read-me "
  "that reproduces every table and figure from the raw files are available at https://github.com/prakash-ukhalkar/banknifty-expiry-volatility-ml and will be deposited in an archive with a persistent identifier upon acceptance; "
  "the derived monthly panels and expiry dates are also supplied as Online Resource 2. Author contributions are on the title page.", after=8)

# ---------------------------------------------------------------- References
H("References")
REFS = [
 "Abadie A, Diamond A, Hainmueller J (2010) Synthetic control methods for comparative case studies: estimating the effect of California's tobacco control program. J Am Stat Assoc 105:493–505. https://doi.org/10.1198/jasa.2009.ap08746",
 "Admati AR, Pfleiderer P (1988) A theory of intraday patterns: volume and price variability. Rev Financ Stud 1:3–40. https://doi.org/10.1093/rfs/1.1.3",
 "Agarwalla SK, Pandey A (2013) Expiration-day effects and the impact of short trading breaks on intraday volatility: evidence from the Indian market. J Futures Mark 33:1046–1070. https://doi.org/10.1002/fut.21632",
 "Amihud Y (2002) Illiquidity and stock returns: cross-section and time-series effects. J Financ Mark 5:31–56. https://doi.org/10.1016/S1386-4181(01)00024-6",
 "Andersen TG, Fusari N, Todorov V (2017) Short-term market risks implied by weekly options. J Finance 72:1335–1386. https://doi.org/10.1111/jofi.12486",
 "Barber BM, Huang X, Odean T, Schwarz C (2022) Attention-induced trading and returns: evidence from Robinhood users. J Finance 77:3141–3190. https://doi.org/10.1111/jofi.13183",
 "Bertrand M, Duflo E, Mullainathan S (2004) How much should we trust differences-in-differences estimates? Q J Econ 119:249–275. https://doi.org/10.1162/003355304772839588",
 "Bryzgalova S, Pavlova A, Sikorskaya T (2023) Retail trading in options and the rise of the big three wholesalers. J Finance 78:3465–3514. https://doi.org/10.1111/jofi.13285",
 "Callaway B, Sant'Anna PHC (2021) Difference-in-differences with multiple time periods. J Econom 225:200–230. https://doi.org/10.1016/j.jeconom.2020.12.001",
 "Conley TG, Taber CR (2011) Inference with \"difference in differences\" with a small number of policy changes. Rev Econ Stat 93:113–125. https://doi.org/10.1162/REST_a_00049",
 "Corwin SA, Schultz P (2012) A simple way to estimate bid-ask spreads from daily high and low prices. J Finance 67:719–760. https://doi.org/10.1111/j.1540-6261.2012.01729.x",
 "Fisher RA (1935) The design of experiments. Oliver and Boyd, Edinburgh",
 "Golez B, Jackwerth JC (2012) Pinning in the S&P 500 futures. J Financ Econ 106:566–585. https://doi.org/10.1016/j.jfineco.2012.06.010",
 "Imbens GW, Rubin DB (2015) Causal inference for statistics, social, and biomedical sciences: an introduction. Cambridge University Press, New York",
 "Narang S, Vij M (2013) Long-term effects of expiration of derivatives on Indian spot volatility. ISRN Econ 2013:718538. https://doi.org/10.1155/2013/718538",
 "Ni SX, Pearson ND, Poteshman AM (2005) Stock price clustering on option expiration dates. J Financ Econ 78:49–87. https://doi.org/10.1016/j.jfineco.2004.08.005",
 "Pagano M (1989) Trading volume and asset liquidity. Q J Econ 104:255–274. https://doi.org/10.2307/2937787",
 "Rambachan A, Roth J (2023) A more credible approach to parallel trends. Rev Econ Stud 90:2555–2591. https://doi.org/10.1093/restud/rdad018",
 "SEBI (2024a) Measures to strengthen equity index derivatives framework for investor protection and market stability. Circular dated 1 October 2024. Securities and Exchange Board of India, Mumbai",
 "SEBI (2024b) Analysis of profit and loss of individual traders dealing in equity futures and options segment. Study. Securities and Exchange Board of India, Mumbai",
 "Stoll HR, Whaley RE (1987) Program trading and expiration-day effects. Financ Anal J 43:16–28. https://doi.org/10.2469/faj.v43.n2.16",
 "Vipul (2005) Futures and options expiration-day effects: the Indian evidence. J Futures Mark 25:1045–1065. https://doi.org/10.1002/fut.20178",
]
for r_ in REFS:
    p = doc.add_paragraph(r_); p.paragraph_format.left_indent = Cm(0.8); p.paragraph_format.first_line_indent = Cm(-0.8); p.paragraph_format.space_after = Pt(3)
    for run_ in p.runs: run_.font.size = Pt(10)
doc.save(OUT / "Manuscript.docx")
print("Manuscript.docx saved; abstract words:", wc)

# ================================================================ Title page
tp = Document(); tp.styles["Normal"].font.name = "Times New Roman"; tp.styles["Normal"].font.size = Pt(11)
def tpP(t, bold=False, after=6):
    p = tp.add_paragraph(); r = p.add_run(t); r.bold = bold; p.paragraph_format.space_after = Pt(after); return p
tpP(TITLE, True, 10)
tpP("Authors", True, 2)
tpP("Prakash Ukhalkar (corresponding author), Department of MCA, Pimpri Chinchwad College of Engineering, Pune, Maharashtra, India. Email: prakash.ukhalkar@pccoepune.org. ORCID: [to be added]", after=2)
tpP("Ravikant Zirmite, Department of MCA, MES Institute of Management and Career Courses (IMCC), Pune, Maharashtra, India. ORCID: [to be added]", after=2)
tpP("Manasi Bhate, Department of MCA, MES Institute of Management and Career Courses (IMCC), Pune, Maharashtra, India. ORCID: [to be added]", after=8)
tpP("Author contributions (CRediT)", True, 2)
tpP("Prakash Ukhalkar: Conceptualization, Methodology, Software, Formal analysis, Data curation, Visualization, Writing – original draft. Ravikant Zirmite: Supervision, Writing – review and editing. "
    "Manasi Bhate: Supervision, Writing – review and editing. All authors approved the final manuscript.", after=8)
tpP("Acknowledgments", True, 2)
tpP("The authors thank Pimpri Chinchwad College of Engineering, Pune, and MES Institute of Management and Career Courses, Pune, for providing computational resources and library access.", after=8)
tpP("Statements and Declarations", True, 2)
tpP("Funding: The authors did not receive support from any organization for the submitted work. Competing interests: The authors have no relevant financial or non-financial interests to disclose.", after=8)
tpP("Abstract, keywords and JEL codes are in the manuscript file.", after=2)
tp.save(OUT / "Title_Page.docx")

# ================================================================ Cover letter
cd = Document(); cd.styles["Normal"].font.name = "Times New Roman"; cd.styles["Normal"].font.size = Pt(11)
def cP(t, after=8): p = cd.add_paragraph(t); p.paragraph_format.space_after = Pt(after); return p
cP("Dear Editor,", 8)
cP(f"We submit \"{TITLE}\" for consideration in Empirical Economics.")
cP("The paper evaluates a regulatory rule that limited each Indian exchange to one weekly index-options expiry. It is a policy-evaluation and measurement paper: we show that a rule-based expiry calendar "
   "misclassifies the treated expiry dates and reverses the headline sign, we rebuild expiry dates from contract-level exchange files, and we estimate effects on two exchanges with a never-treated placebo group, "
   "a daily dose-response and exact randomization inference suited to six units, plus a smoothness-based pre-trend sensitivity analysis. The main findings are that turnover on the retired indices collapsed, "
   "the expiry-day share of the remainder rose, expiry-day turnover in levels did not rise, and activity migrated to the retained weeklies by an amount that is bounded but not point-identified.")
cP("We believe the paper fits the journal's interest in treatment-effect estimation, policy evaluation and measurement, and its emphasis on replicability. All code, derived panels and a read-me that reproduces every "
   "table and figure from public raw exchange files are available, and we will deposit them in an archive with a persistent identifier upon acceptance.")
cP("The manuscript is not under consideration elsewhere. An earlier version of this work, based on a rule-based expiry calendar and with different conclusions, was submitted elsewhere and was not published; "
   "this manuscript supersedes it and uses a different design and data. All authors have approved the submission. Use of an AI tool for code and drafting is documented in Section 4.5.")
cP("Sincerely,", 2); cP("Prakash Ukhalkar (corresponding author) on behalf of all authors")
cd.save(OUT / "Cover_Letter.docx")

# ================================================================ Online Resource 1
sd = Document(); sd.styles["Normal"].font.name = "Times New Roman"; sd.styles["Normal"].font.size = Pt(10.5)
sd.add_paragraph().add_run(f"Online Resource 1: Supplementary tables for \"{TITLE}\". Corresponding author: Prakash Ukhalkar, prakash.ukhalkar@pccoepune.org").bold = True
def sH(t): p = sd.add_paragraph(); p.add_run(t).bold = True
def sT(rows, hdr):
    t = sd.add_table(rows=1, cols=len(hdr)); t.style = "Table Grid"
    for i, h in enumerate(hdr): t.rows[0].cells[i].text = h
    for r_ in rows:
        c = t.add_row().cells
        for i, v in enumerate(r_): c[i].text = str(v)
    sd.add_paragraph()
sH("Table S1. Interrupted-time-series interactions (expiry week × regime; baseline Thursday-weekly), p-values")
names = {"its_return_model": "Return", "its_absreturn_model": "|Return|", "its_rolling_vol_model": "Rolling volatility", "its_parkinson_vol_model": "Parkinson volatility", "its_garman_klass_vol_model": "Garman-Klass volatility"}
regs = [k for k in cl["its_return_model"]["params"] if k.startswith("EW_x")]
sT([[names[k]] + [f"{cl[k]['params'][r_]:+.5f} (p = {cl[k]['p_values'][r_]:.3f})" for r_ in regs] for k in names], ["Outcome"] + [r_.replace("EW_x_", "") for r_ in regs])
sH("Table S2. Clean weekday-only contrasts (expiry week × new weekday regime)")
sT([[lab, y, f"{v['coef']:+.5f}", f"{v['se']:.5f}", f"{v['p']:.3f}", d["n"]] for lab, d in its.items() for y, v in d.items() if y != "n"], ["Contrast", "Outcome", "Coefficient", "Std. error", "p", "N"])
sH("Table S3. Walk-forward directional accuracy (five expanding-window folds)")
sT([[k[11:], f"{v['accuracy_mean']:.3f}", f"[{v['ci_2.5']:.3f}, {v['ci_97.5']:.3f}]"] for k, v in wf.items() if k.startswith("DirAcc_CI")], ["Model", "Accuracy", "95% bootstrap CI"])
sH("Table S4. Window sensitivity of the Bank Nifty versus Nifty difference-in-differences (log points)")
sT([[w, f"{v['lt']:+.2f}", f"{v['le']:+.2f}", f"{v['ls']:+.2f}"] for w, v in rb["window_sensitivity"].items()], ["Window", "Total turnover", "Expiry-day turnover", "Expiry-day share"])
sH("Table S5. Bank Nifty before/after without a control (HAC standard errors; log points)")
sT([[y, f"{v['coef']:+.2f}", f"{v['se']:.2f}"] for y, v in rb["bn_only_before_after"].items()], ["Outcome", "Coefficient", "Std. error"])
sd.save(OUT / "Online_Resource_1.docx")
print("Title_Page, Cover_Letter, Online_Resource_1 saved")
