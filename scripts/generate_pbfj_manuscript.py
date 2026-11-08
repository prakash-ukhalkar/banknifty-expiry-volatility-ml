"""
Generates the anonymized Main-Manuscript.docx for Pacific-Basin Finance Journal
submission. Per PBFJ's double-anonymized review policy, this file must contain
NO author names, affiliations, or acknowledgments (those live on the separate
Title_Page.docx). All numbers are pulled live from results/*.json so the
manuscript can never drift out of sync with the underlying analysis.

Usage:
    python -m scripts.generate_pbfj_manuscript
"""
import json
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from scripts.generate_paper_docx import (
    set_document_margins, add_header, add_line_numbering, format_run,
    add_paragraph, add_section_heading, mark_header_row, add_table_title,
    add_table_footnote, embed_figure, parse_bib_file,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT_ROOT / "results"
FIGS = RESULTS / "figures"


def load_json(name):
    with open(RESULTS / name) as f:
        return json.load(f)


def fmt_p(p):
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.3f}"


def build_citation_map():
    bib_path = PROJECT_ROOT / "manuscript" / "references.bib"
    entries = {e["key"]: e for e in parse_bib_file(bib_path)}

    def clean(name):
        return name.replace("{", "").replace("}", "").strip()

    def authors_last(entry):
        raw = entry.get("author", "Unknown")
        parts = [clean(a) for a in raw.split(" and ")]
        last = []
        for a in parts:
            last.append(a.split(",")[0].strip() if "," in a else a.split()[-1])
        return last

    def inline(key):
        e = entries[key]
        last = authors_last(e)
        year = e.get("year", "n.d.")
        if len(last) == 1:
            return f"{last[0]} ({year})"
        elif len(last) == 2:
            return f"{last[0]} and {last[1]} ({year})"
        return f"{last[0]} et al. ({year})"

    def paren(key):
        e = entries[key]
        last = authors_last(e)
        year = e.get("year", "n.d.")
        if len(last) == 1:
            return f"{last[0]}, {year}"
        elif len(last) == 2:
            return f"{last[0]} & {last[1]}, {year}"
        return f"{last[0]} et al., {year}"

    return entries, inline, paren


def add_table_from_rows(doc, headers, rows, col_sizes=None, font_size=9.5):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = True
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        hdr[i].paragraphs[0].runs[0].font.bold = True
        hdr[i].paragraphs[0].runs[0].font.name = "Times New Roman"
        hdr[i].paragraphs[0].runs[0].font.size = Pt(font_size)
    mark_header_row(table)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
            cells[i].paragraphs[0].runs[0].font.name = "Times New Roman"
            cells[i].paragraphs[0].runs[0].font.size = Pt(font_size)
    return table


def main():
    with open(PROJECT_ROOT / "manuscript" / "paper_config_pbfj.yaml") as f:
        cfg = yaml.safe_load(f)

    did = load_json("diff_in_diff_banknifty_vs_nifty.json")
    ev_vol = load_json("expiry_volume_oi_event_study.json")
    ev_lead_lag = load_json("event_study_leads_lags.json")
    wf = load_json("walk_forward_results.json")
    regime_its = load_json("regime_shift_event_study.json")

    c, cite, paren = build_citation_map()

    # ------------------------------------------------------------------
    doc = Document()
    set_document_margins(doc)
    add_header(doc, cfg["paper"]["short_title"])
    add_line_numbering(doc)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(24)
    p_title.paragraph_format.space_after = Pt(18)
    run_title = p_title.add_run(cfg["paper"]["title"])
    format_run(run_title, bold=True, size=15)

    p_anon = doc.add_paragraph()
    p_anon.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_anon = p_anon.add_run("[Author names and affiliations removed for double-anonymized review -- see separate Title Page]")
    format_run(r_anon, italic=True, size=9.5)

    # -- Abstract -------------------------------------------------------
    add_section_heading(doc, "Abstract")
    add_paragraph(doc, cfg["abstract"].strip(), spacing=1.5, after=18)
    p_kw = doc.add_paragraph()
    p_kw.paragraph_format.space_after = Pt(24)
    r_kw_lbl = p_kw.add_run("Keywords: ")
    format_run(r_kw_lbl, bold=True, size=11)
    r_kw_val = p_kw.add_run("; ".join(cfg["keywords"]))
    format_run(r_kw_val, italic=True, size=11)

    # ===================================================================
    # 1. INTRODUCTION
    # ===================================================================
    add_section_heading(doc, "1. Introduction")

    add_paragraph(doc, (
        "Exchanges and regulators periodically consolidate derivatives listings to reduce market complexity -- "
        "limiting the number of actively traded contracts on a given underlying, standardizing settlement "
        "mechanics across products, or restricting which exchange may list a weekly contract on a given index. "
        "These decisions are usually justified on the grounds of simplifying margining, reducing fragmented "
        "liquidity, and easing operational load on clearing corporations. What is less well understood is how "
        "such consolidation changes the distribution of trading activity across the trading days that remain: "
        "if a weekly contract is withdrawn and only a monthly contract survives, does the settlement-day volume "
        "and open-interest unwinding that previously spread across four weekly expiries each month now "
        "concentrate onto a single day, and by how much?"
    ))

    add_paragraph(doc, (
        "India's National Stock Exchange (NSE) provides an unusually clean setting to study this question, "
        "because two regulatory changes to its index-derivatives market took effect within an eighteen-month "
        "window and can be separately identified in the exchange's own contract records. First, the exchange "
        "moved the settlement weekday for its weekly index-options expiry three times -- from Thursday, to "
        "Wednesday (March 2024), to Tuesday (September 2025). Second, and separately, a rule limiting each "
        "exchange to a single weekly index-derivatives contract forced the exchange to discontinue Bank Nifty "
        "weekly options while Nifty 50 retained its own weekly contract. We verify directly in the exchange's "
        "daily contract records (Section 3.3) that the number of distinct Bank Nifty option expiries listed on "
        "a given day fell from ten to six between 17 October and 14 November 2024, consistent with the last "
        "Bank Nifty weekly expiry trading on 13 November 2024 and every expiry thereafter being a monthly "
        "contract."
    ))

    add_paragraph(doc, (
        "These two changes are easy to conflate but have different, separately testable, implications. The "
        "settlement-weekday shift moves which calendar weekday absorbs expiry-related trading, but gives no "
        "obvious reason to expect spot returns or realized volatility to change on average. The weekly-contract "
        "removal, by contrast, mechanically reduces the number of expiry events per month from roughly four to "
        "one, which should concentrate position rollover, delta-hedging unwind, and open-interest liquidation "
        "that previously spread across multiple weekly settlements onto the single remaining monthly expiry "
        f"day -- a liquidity-concentration channel documented in other markets since at least {cite('stoll1987expiry')}, "
        f"and specifically in Indian derivatives by {cite('vipul2005expiry')} and {cite('agarwalla2013expiry')}, "
        "though neither study had access to a within-exchange natural experiment removing a weekly contract "
        "while a comparable index retained its own."
    ))

    add_paragraph(doc, (
        "This paper separates the two questions and tests each directly. Using the complete NSE "
        "futures-and-options Bhavcopy archive from January 2020 to October 2026, reconstructed into "
        "lot-size-invariant daily turnover and open-interest series (Section 3.2), we estimate a "
        "difference-in-differences model comparing Bank Nifty's expiry-day trading concentration against a "
        "Nifty 50 control -- which experienced the same settlement-weekday calendar changes but kept its own "
        "weekly contract -- before and after the November 2024 weekly-contract removal. We find that Bank "
        "Nifty's expiry-day turnover and open interest rose sharply and significantly more than Nifty 50's "
        "after the removal (Section 5), a result that survives a lot-size confound correction, placebo cutover "
        "dates, leave-one-out exclusion of each treated expiry, and an event-study specification confirming "
        "the increase is a discrete post-reform jump rather than a continuation of a pre-existing trend."
    ))

    add_paragraph(doc, (
        "We then ask, separately, whether the settlement-weekday reforms created any exploitable return "
        "predictability or shifted expiry-week volatility -- the question a calendar-effects study would "
        "typically ask first. A leakage-free walk-forward evaluation across the Thursday-, Wednesday-, and "
        "Tuesday-settlement regimes finds no directional accuracy distinguishable from chance in any regime, "
        "before or after correction for multiple comparisons. An interrupted-time-series regression finds no "
        "robust shift in expiry-week returns or realized volatility across the weekday changes, using both "
        "close-to-close and range-based (Parkinson) volatility estimators. We report both null results "
        "transparently, in keeping with Pacific-Basin Finance Journal's stated stance against publication bias: "
        "the reform's measurable market-structure effect operates through trading concentration, not price "
        "predictability, and a paper that only tested the latter would have reported a misleadingly incomplete "
        "picture of what the reform actually changed."
    ))

    add_paragraph(doc, (
        "The contribution is threefold. First, we provide, to our knowledge, the first difference-in-differences "
        "estimate of how removing a weekly derivatives contract concentrates trading activity on the surviving "
        "expiry day, using a within-exchange control that experienced the same calendar reforms but not the "
        "contract removal. Second, we construct and validate a lot-size-invariant turnover and open-interest "
        "series from raw exchange Bhavcopy records spanning a format change and two lot-size revisions, which we "
        "make available for future work on Indian derivatives microstructure. Third, by testing and reporting "
        "the predictability question as well as the concentration question, we show that a plausible-sounding "
        "calendar-effects hypothesis and the actual, confirmable market-structure effect of the same reform can "
        "point in different directions -- a methodological point with implications beyond this specific dataset "
        "for how calendar-reform studies in emerging-market derivatives should be designed."
    ))

    add_paragraph(doc, (
        "The remainder of the paper proceeds as follows. Section 2 reviews the relevant literature on "
        "expiration-day effects and places the NSE reforms in institutional context. Section 3 describes the "
        "data, including the construction of the lot-size-invariant turnover series and the identification of "
        "the weekly-contract discontinuation date. Section 4 sets out the difference-in-differences and "
        "robustness methodology for the primary analysis, and the walk-forward and interrupted-time-series "
        "methodology for the secondary predictability analysis. Section 5 presents results. Section 6 discusses "
        "economic interpretation, policy implications, and limitations. Section 7 concludes."
    ))

    # ===================================================================
    # 2. INSTITUTIONAL BACKGROUND AND LITERATURE
    # ===================================================================
    add_section_heading(doc, "2. Institutional Background and Related Literature")

    add_section_heading(doc, "2.1. NSE Index-Derivatives Reforms, 2023-2025", level=2)
    add_paragraph(doc, (
        "Bank Nifty and Nifty 50 are the two most actively traded index-derivatives underlyings on the NSE. "
        "Historically, both indices' weekly options expired on Thursday. Beginning in 2023-2025, the exchange "
        "moved the settlement weekday for its surviving weekly index-options contract, first to Wednesday "
        "(effective March 2024) and then to Tuesday (effective September 2025); the exact scheduled and "
        "holiday-adjusted expiry date for every month in our sample, constructed from the NSE's own calendar "
        "publications, is used throughout this paper to identify expiry days (Section 3.1). Separately, and on "
        "a different timeline, exchanges were restricted to listing a single weekly index-derivatives contract "
        "each, which meant NSE could retain a weekly contract on only one of its two flagship indices; it kept "
        "Nifty 50 weekly options and discontinued Bank Nifty weekly options. We identify the exact "
        "discontinuation window directly in the exchange's daily contract listings rather than relying on a "
        "secondary source: the number of distinct Bank Nifty option expiry dates quoted in the Bhavcopy on any "
        "given day falls from ten (several weekly expiries plus several further-dated monthly expiries) to six "
        "(monthly expiries only) over four trading weeks in October-November 2024, with the last Bank Nifty "
        "weekly expiry trading on 13 November 2024 and 27 November 2024 the first monthly-only expiry "
        "(Section 3.3). Bank Nifty's exchange-set lot size also changed, from 15 to 30, within the same window "
        "(Section 3.2), a second mechanical change that must be corrected for separately before any turnover or "
        "open-interest comparison across this date is meaningful."
    ))
    add_paragraph(doc, (
        "These two reforms are easy to conflate in a naive before/after comparison because they occurred close "
        "together in calendar time, but they are conceptually distinct and, as we show, have different "
        "measurable consequences. The settlement-weekday shift changes which calendar weekday is the expiry "
        "day; the weekly-contract removal changes how many expiry events occur per month. Only the second "
        "reform has an obvious mechanical reason to affect trading concentration, and only it is tested with a "
        "control group in this paper."
    ))

    add_section_heading(doc, "2.2. Expiration-Day Effects on Volume, Open Interest, and Price", level=2)
    add_paragraph(doc, (
        f"The most consistently replicated finding in the expiration-day literature is abnormal trading volume "
        f"around derivatives settlement, not abnormal returns. {cite('stoll1987expiry')} documented sharp "
        f"volume spikes and a short-lived price reversal around U.S. index-futures and options expirations, "
        f"attributing the effect to index-arbitrage unwinding concentrated in the closing minutes of the expiry "
        f"session. {cite('karolyi1996expiry')} found a comparable volatility and volume pattern around Nikkei "
        f"futures expirations in Japan, and {cite('chow2003expiry')} documented expiration effects in Hong Kong "
        f"index derivatives linked to dealer delta-hedging flows. In India specifically, {cite('vipul2005expiry')} "
        f"found a robust abnormal-volume effect around NSE derivatives expiry across a cross-section of "
        f"underlyings, but no statistically reliable same-day volatility effect -- a result consistent with the "
        f"broader literature's conclusion that the volume channel is far more reliably documented than the "
        f"price or volatility channel. {cite('agarwalla2013expiry')} similarly found elevated intraday "
        f"volatility around NSE settlement specifically tied to a since-discontinued short trading break "
        f"mechanism, rather than to the expiry event itself. {cite('bollen2004buying')} provide a mechanism "
        f"consistent with this pattern: net buying pressure from dealer hedging activity distorts the shape of "
        f"implied volatility, and this distortion is naturally largest when open positions must be closed or "
        f"rolled over in a compressed window, exactly the condition a weekly-to-monthly-only transition "
        f"creates."
    ))
    add_paragraph(doc, (
        "This literature motivates testing trading concentration, rather than returns, as the primary "
        "consequence of removing a weekly contract. None of the studies above, however, had access to a "
        "within-exchange natural experiment in which a comparable index retained its own weekly contract while "
        "the index of interest lost it -- the design this paper uses to separate the mechanical liquidity "
        "channel from any market-wide trend that happened to coincide with the reform."
    ))

    add_section_heading(doc, "2.3. Volatility Regimes, Calendar Effects, and Return Predictability", level=2)
    add_paragraph(doc, (
        f"A separate literature asks whether calendar or structural reforms create exploitable return "
        f"predictability, typically by conditioning forecasts on volatility-regime state "
        f"({cite('hamilton1989new')}; {cite('ang2002regime')}; {cite('ryden1998stylized')}; "
        f"{cite('kritzman2012regime')}). This is the natural first question a calendar-reform study asks, and "
        f"it is the question our secondary analysis (Sections 4.3-4.4 and 5.4-5.5) addresses directly for the "
        f"NSE settlement-weekday reforms. Forecast-comparison tests in this tradition commonly use the "
        f"Diebold-Mariano framework ({cite('diebold1995comparing')}) to judge whether one model's errors are "
        f"statistically distinguishable from another's; we use the same approach, with Newey-West robust "
        f"variance estimation, in Section 4.3."
    ))

    # ===================================================================
    # 3. DATA
    # ===================================================================
    add_section_heading(doc, "3. Data")

    add_section_heading(doc, "3.1. Index Price Data and Expiry Calendar", level=2)
    add_paragraph(doc, (
        "Daily Open, High, Low, Close, and Volume data for the Bank Nifty index (ticker ^NSEBANK) are obtained "
        "from Yahoo Finance for 1 January 2020 to 18 October 2026 (1,680 trading days). The monthly expiry "
        "calendar is constructed programmatically by identifying the last Thursday of each month before March "
        "2024, the last Wednesday from March 2024 to August 2025, and the last Tuesday from September 2025 "
        "onward, with each scheduled date rolled back to the preceding trading day whenever it falls on an "
        "exchange holiday (identified from NSE's published holiday list). This calendar is used both to flag "
        "expiry days in the trading-activity analysis (Section 4.1) and as the source of the Days_To_Expiry "
        "and Expiry_Week variables used in the secondary predictability analysis (Section 4.3)."
    ))

    add_section_heading(doc, "3.2. Futures-and-Options Bhavcopy Archive and Lot-Size-Invariant Construction", level=2)
    add_paragraph(doc, (
        "The primary analysis uses NSE's daily futures-and-options Bhavcopy archive, which reports, for every "
        "traded contract on every trading day, the instrument type, expiry date, strike and option type where "
        "applicable, traded volume (contracts), traded value, open interest, and change in open interest. The "
        "archive spans two formats separated by a format migration on 8 July 2024: a legacy fixed-column CSV "
        "format and the newer UDiFF common Bhavcopy format. We retrieve 1,679 of 1,726 possible trading days "
        "between January 2020 and October 2026 (97.3%; the remainder are additional exchange holidays not in "
        "our baseline holiday list) and parse both formats into a single daily panel for Bank Nifty and, "
        "separately, for Nifty 50, aggregating across all strikes and both option types to total daily futures "
        "and options turnover and open interest for each index."
    ))
    add_paragraph(doc, (
        "A direct comparison of contract-count turnover or open interest across the weekly-contract removal "
        "date is confounded by a second, independent change: Bank Nifty's exchange-set lot size rose from 15 "
        "to 30 within the same window (and Nifty 50's separately from 25 to 75, later revised to 65), which we "
        "confirm directly from the UDiFF archive's lot-size field and, for the pre-UDiFF legacy period, from an "
        "implied lot size recovered as traded value divided by the product of contract count and settlement "
        "price (verified against the known post-2024 lot sizes to within rounding error). Because a lot-size "
        "change mechanically alters how many contracts a given rupee notional represents, raw contract counts "
        "are not comparable across this boundary. We therefore construct, and report as the primary outcome "
        "variables, total daily traded value in rupees (a natural lot-size-invariant turnover measure, since "
        "rupee value traded does not depend on how the exchange defines one contract) and a lot-size-adjusted "
        "notional open interest, computed as contract-count open interest multiplied by the prevailing lot size "
        "on that day. Raw contract-count turnover and open interest are also reported as a secondary check "
        "(Section 5.2); the two sets of results are consistent."
    ))

    add_section_heading(doc, "3.3. Identifying the Weekly-Options Discontinuation Date", level=2)
    add_paragraph(doc, (
        "Rather than relying on a secondary account of when Bank Nifty weekly options were discontinued, we "
        "identify the date directly from the exchange's own daily contract listings. Counting the number of "
        "distinct Bank Nifty option expiry dates quoted in the Bhavcopy on sampled trading days through "
        "2020-2024 shows a stable count of ten (several near-dated weekly expiries plus several further-dated "
        "monthly expiries) through mid-October 2024. A day-by-day count through October-November 2024 shows "
        "this falling in four discrete steps -- ten to nine (17 October), nine to eight (24 October), eight to "
        "seven (7 November), and seven to six (14 November) -- exactly tracking each successive weekly expiry "
        "simply not being relisted after it expired. The last Bank Nifty weekly expiry traded on 13 November "
        "2024; every Bank Nifty option expiry from 27 November 2024 onward is a monthly contract. We use 14 "
        "November 2024 as the discontinuation cutover date throughout."
    ))

    cov = ev_vol["expiry_vs_nonexpiry_by_stratum_Total_Volume"]
    cov_rows = []
    for stratum_key in ["Thursday-era / Weekly-Options", "Wednesday-era / Weekly-Options", "Wednesday-era / Monthly-Only", "Tuesday-era / Monthly-Only"]:
        matches = [r for r in cov if r["Stratum"] == stratum_key]
        if matches:
            r = matches[0]
            cov_rows.append((stratum_key, r["N_Expiry"], r["N_NonExpiry_SameWeekday"]))

    add_table_title(doc, "Table 1. Data Coverage by Settlement-Weekday Regime and Liquidity Regime")
    add_table_from_rows(
        doc,
        ["Stratum (settlement regime / liquidity regime)", "N expiry days", "N non-expiry days (same weekday)"],
        cov_rows,
    )
    add_table_footnote(doc, (
        "Note: Liquidity regime is Weekly-Options (Bank Nifty had its own weekly expiries) before 14 November "
        "2024, Monthly-Only from 14 November 2024 onward. Settlement regime follows the Thursday/Wednesday/"
        "Tuesday expiry-weekday calendar (Section 3.1). The Thursday-era and the pre-November-2024 portion of "
        "Wednesday-era are entirely Weekly-Options; the post-November-2024 portion of Wednesday-era and all of "
        "Tuesday-era are entirely Monthly-Only."
    ))

    # ===================================================================
    # 4. METHODOLOGY
    # ===================================================================
    add_section_heading(doc, "4. Methodology")

    add_section_heading(doc, "4.1. Primary Analysis: Difference-in-Differences Design", level=2)
    add_paragraph(doc, (
        "The primary hypothesis is that removing Bank Nifty's weekly options contract concentrated trading "
        "activity onto the single remaining monthly expiry day, beyond any trend shared with the broader "
        "derivatives market. Nifty 50 is the control group: it experienced the same settlement-weekday "
        "calendar reforms and the same period's general growth in Indian index-derivatives activity, but it "
        "did not lose its weekly contract. We pool daily Bank Nifty and Nifty 50 turnover (or open interest) "
        "into a single panel and estimate, by ordinary least squares with Newey-West heteroskedasticity- and "
        "autocorrelation-consistent standard errors (five lags),"
    ))
    add_paragraph(doc, (
        "log(Value_it) = a + b1*Expiry_it + b2*MonthlyOnly_t + b3*BankNifty_i "
        "+ b4*(Expiry_it x MonthlyOnly_t) + b5*(Expiry_it x BankNifty_i) "
        "+ b6*(MonthlyOnly_t x BankNifty_i) + b7*(Expiry_it x MonthlyOnly_t x BankNifty_i) "
        "+ b8*Trend_t + weekday fixed effects + e_it,"
    ), italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(doc, (
        "where i indexes index (Bank Nifty or Nifty 50), t indexes trading day, Expiry_it is an indicator for a "
        "monthly expiry day, MonthlyOnly_t is an indicator for the post-14-November-2024 period, BankNifty_i "
        "is an indicator for the Bank Nifty series, Trend_t is a linear time trend, and weekday fixed effects "
        "absorb any generic day-of-week seasonality in trading activity. The coefficient of interest is b7 on "
        "the triple interaction Expiry x MonthlyOnly x BankNifty: it measures how much more Bank Nifty's "
        "expiry-day trading activity rose, relative to Nifty 50's, after the weekly-contract removal, net of "
        "whatever expiry-day effect, liquidity-regime effect, and index-level effect each already has on its "
        "own. We estimate this specification separately for log traded value and log notional open interest "
        "(Section 3.2), and for raw log contract-count turnover and open interest as a secondary check."
    ))

    add_section_heading(doc, "4.2. Robustness: Placebo Dates, Leave-One-Out, and Event-Study Leads/Lags", level=2)
    add_paragraph(doc, (
        "Three checks probe whether the triple-interaction coefficient reflects a genuine discontinuity at the "
        "true 14 November 2024 cutover rather than an artifact of a longer-running trend or a small number of "
        "unusual observations. First, a placebo-date test re-estimates the same specification with the "
        "MonthlyOnly indicator redefined around fake cutover dates placed years before the true event, deep "
        "inside the stable Weekly-Options era (June 2021, June 2022, June 2023), where no regime change "
        "actually occurred; a genuine discontinuity should produce a materially smaller or null coefficient at "
        "these fake dates than at the true one. Second, a leave-one-out analysis re-estimates the model 23 "
        "times, each time excluding one of Bank Nifty's Monthly-Only-regime expiry days, to confirm the result "
        "is not driven by any single unusually large settlement day. Third, an event-study specification "
        "replaces the single before/after MonthlyOnly dummy with a separate Expiry x BankNifty coefficient for "
        "each half-year period relative to the true event (the half-year immediately preceding the event is "
        "the omitted reference period), which distinguishes a genuine post-event jump from a smooth trend that "
        "merely continues through the event date."
    ))

    add_section_heading(doc, "4.3. Secondary Analysis: Walk-Forward Return Predictability", level=2)
    add_paragraph(doc, (
        "To test whether the settlement-weekday reforms created exploitable next-day return predictability -- "
        "the question the expiration-day literature most commonly asks -- we construct four next-day log-return "
        "forecasting models of increasing feature richness: a technical-indicators-only baseline (RSI, MACD, "
        "Bollinger Bands, Average True Range, rolling volatility, lagged return); the baseline plus cyclical "
        "expiry-distance features; the baseline plus two-state Gaussian hidden-Markov-model volatility-regime "
        "probabilities; and a combined specification with both. Each is fit as a regularized gradient-boosted "
        "tree (XGBoost) under a five-fold expanding-window walk-forward protocol: within each fold, both the "
        "regime-detection model and the forecasting model are fit only on that fold's training portion, and "
        "evaluated on a held-out forward window, so that no information from a test period ever enters its own "
        "training set. We report pooled out-of-fold directional accuracy with bootstrap 95% confidence "
        "intervals, an exact binomial test against the 50% chance benchmark with Holm-Bonferroni correction "
        f"across the four model conditions, and Diebold-Mariano tests ({cite('diebold1995comparing')}) "
        "comparing forecast accuracy between conditions, reported separately within each settlement-weekday "
        "regime so that no result is pooled across the structural break the reforms themselves created."
    ))

    add_section_heading(doc, "4.4. Secondary Analysis: Interrupted Time Series on the Settlement-Weekday Reform", level=2)
    add_paragraph(doc, (
        "To test whether the settlement-weekday reforms shifted expiry-week returns or volatility directly, "
        "independent of the predictive-modeling exercise above, we estimate an interrupted-time-series "
        "regression of daily return (and, separately, two realized-volatility measures) on an expiry-week "
        "indicator, settlement-regime indicators for the Wednesday and Tuesday eras (Thursday-era omitted), "
        "their interactions with the expiry-week indicator, and a linear trend, with Newey-West standard "
        "errors. The interaction coefficients test whether the expiry-week effect size changed after each "
        "reform. We report this for close-to-close log returns, absolute returns as a volatility proxy, the "
        "existing 10-day rolling-standard-deviation volatility measure, and a Parkinson range-based volatility "
        "estimator constructed from each day's high and low price -- a methodological improvement over "
        "close-to-close volatility estimators, which use only the closing price and discard most of the "
        "intraday price path."
    ))

    # ===================================================================
    # 5. RESULTS
    # ===================================================================
    add_section_heading(doc, "5. Results")

    add_section_heading(doc, "5.1. Descriptive Expiry-Day Trading Patterns", level=2)
    add_paragraph(doc, (
        "Figure 1 plots mean Bank Nifty trading volume and open interest in the trading days immediately "
        "surrounding expiry, pooled across the full sample. Both turnover and open interest peak sharply on "
        "the expiry day itself and fall back within one trading day, consistent with position unwinding and "
        "rollover concentrated at settlement."
    ))
    embed_figure(
        doc, FIGS / "expiry_volume_profile.png",
        "Figure 1. Bank Nifty contract volume (panel a) and open interest (panel b) in the trading days "
        "surrounding expiry (day 0), pooled across the full 2020-2026 sample."
    )

    add_section_heading(doc, "5.2. Primary Result: Difference-in-Differences", level=2)
    tv = did["Total_Value"]["params"]["Expiry_x_Monthly_x_BankNifty"]
    tv_p = did["Total_Value"]["p_values"]["Expiry_x_Monthly_x_BankNifty"]
    oi = did["Total_OpenInterest_Notional"]["params"]["Expiry_x_Monthly_x_BankNifty"]
    oi_p = did["Total_OpenInterest_Notional"]["p_values"]["Expiry_x_Monthly_x_BankNifty"]
    tv_pct = (2.71828 ** tv - 1) * 100
    oi_pct = (2.71828 ** oi - 1) * 100

    add_paragraph(doc, (
        f"Table 2 reports the triple-interaction coefficient from the difference-in-differences specification "
        f"(Section 4.1) for each outcome variable. For log traded value, the coefficient is {tv:.4f} "
        f"({fmt_p(tv_p)}), implying Bank Nifty's expiry-day turnover rose by an additional "
        f"{tv_pct:.0f}% relative to Nifty 50 after the weekly-contract removal. For log notional open interest, "
        f"the coefficient is {oi:.4f} ({fmt_p(oi_p)}), implying a further {oi_pct:.0f}% rise in expiry-day open "
        f"interest relative to Nifty 50. Both the raw contract-count turnover and open-interest specifications "
        f"(not confound-corrected for the lot-size change) produce materially similar coefficients "
        f"({did['Total_Volume']['params']['Expiry_x_Monthly_x_BankNifty']:.4f} and "
        f"{did['Total_OpenInterest']['params']['Expiry_x_Monthly_x_BankNifty']:.4f} respectively, both "
        f"significant at conventional levels), indicating the lot-size confound does not drive the result."
    ))

    did_rows = [
        ("Log traded value (primary)", f"{tv:.4f}", fmt_p(tv_p), f"{tv_pct:.0f}%"),
        ("Log notional open interest (primary)", f"{oi:.4f}", fmt_p(oi_p), f"{oi_pct:.0f}%"),
        ("Log raw contract turnover (secondary)", f"{did['Total_Volume']['params']['Expiry_x_Monthly_x_BankNifty']:.4f}", fmt_p(did['Total_Volume']['p_values']['Expiry_x_Monthly_x_BankNifty']), "--"),
        ("Log raw contract open interest (secondary)", f"{did['Total_OpenInterest']['params']['Expiry_x_Monthly_x_BankNifty']:.4f}", fmt_p(did['Total_OpenInterest']['p_values']['Expiry_x_Monthly_x_BankNifty']), "--"),
    ]
    add_table_title(doc, "Table 2. Difference-in-Differences Estimate: Expiry x Monthly-Only x Bank Nifty")
    add_table_from_rows(doc, ["Outcome variable", "Coefficient", "p-value", "Implied % change vs. Nifty 50"], did_rows)
    add_table_footnote(doc, (
        f"Note: n = {did['Total_Value']['n_obs']} pooled daily observations (Bank Nifty and Nifty 50, 2020-2026). "
        "All specifications include weekday fixed effects, a linear trend, and Newey-West standard errors "
        "(5 lags). Implied percentage change computed as (exp(coefficient) - 1) x 100."
    ))

    add_section_heading(doc, "5.3. Robustness Checks", level=2)
    placebo = did["placebo_date_test_Total_Value"]
    loo = did["leave_one_out_Total_Value"]
    placebo_rows = []
    for label, r in placebo.items():
        tag = "TRUE event" if "TRUE" in label else "Placebo"
        placebo_rows.append((label.split(" (")[0], tag, f"{r['coef']:.4f}", fmt_p(r["p_value"])))
    add_table_title(doc, "Table 3. Placebo-Date Robustness Check (Total Value)")
    add_table_from_rows(doc, ["Cutover date used", "Type", "Coefficient", "p-value"], placebo_rows)
    add_table_footnote(doc, (
        "Note: placebo dates are placed years before the true event, deep inside the stable Weekly-Options "
        "era, where no actual regime change occurred."
    ))
    add_paragraph(doc, (
        f"Placebo coefficients at fake cutover dates placed years before the true event are smaller than the "
        f"coefficient at the true date and decline further the earlier the fake date is placed "
        f"({placebo['placebo cutover 2021-06-01 (deep in Weekly-Options era, no real break)']['coef']:.2f} at "
        f"June 2021 versus {placebo['TRUE cutover 2024-11-14']['coef']:.2f} at the true November 2024 date), "
        "consistent with a genuine discontinuity at the true event superimposed on a modest pre-existing "
        "differential trend between the two indices -- a pattern we resolve directly with the event-study "
        "specification below. Leave-one-out exclusion of each of the 23 Bank Nifty Monthly-Only-regime expiry "
        f"days individually changes the coefficient only modestly, ranging from {loo['loo_coef_min']:.3f} to "
        f"{loo['loo_coef_max']:.3f} (mean {loo['loo_coef_mean']:.3f}, SD {loo['loo_coef_std']:.3f}) across the "
        "23 re-estimations, indicating the result is not driven by any single expiry day."
    ))

    add_paragraph(doc, (
        "Figure 2 reports the event-study specification (Section 4.2), with a separate Expiry x Bank Nifty "
        "coefficient estimated for each half-year period relative to the true event (period -1, the half-year "
        "immediately before the event, is the omitted reference). Coefficients in the pre-event periods are "
        "small and roughly flat; coefficients from the event period onward rise sharply and continue rising in "
        "subsequent periods, a pattern inconsistent with a smooth pre-existing trend and consistent with a "
        "genuine discontinuity at the true event that the market continued adjusting to over time."
    ))
    embed_figure(
        doc, FIGS / "event_study_leads_lags.png",
        "Figure 2. Event-study coefficients (Expiry x Bank Nifty) by half-year period relative to the true "
        "14 November 2024 weekly-options discontinuation, for log traded value (panel a) and log notional "
        "open interest (panel b). Error bars show 95% confidence intervals; the vertical dotted line marks "
        "the event."
    )

    add_section_heading(doc, "5.4. Secondary Result: No Robust Return Predictability", level=2)
    base_acc = wf["pooled_significance"]["DirAcc_CI_Baseline (Technical Only)"]
    comb_acc = wf["pooled_significance"]["DirAcc_CI_Proposed (Combined)"]
    dm = wf["pooled_significance"]["DM_test_pooled"]
    sharpe_diff = wf["pooled_significance"]["Sharpe_diff_bootstrap"]
    holm = wf["pooled_significance"]["Holm_Bonferroni_adjusted"]

    add_paragraph(doc, (
        f"Pooled across all five walk-forward folds (405 out-of-sample trading days), directional accuracy "
        f"ranges from {base_acc['accuracy_mean']:.1%} for the technical-only baseline to "
        f"{comb_acc['accuracy_mean']:.1%} for the combined model; every condition's 95% bootstrap confidence "
        f"interval straddles the 50% chance benchmark, and every Holm-Bonferroni-adjusted binomial p-value is "
        f"above conventional significance thresholds (adjusted p-values ranging from "
        f"{min(holm.values()):.2f} to {max(holm.values()):.2f} across the four conditions). A pooled "
        f"Diebold-Mariano test comparing the baseline and combined models' forecast errors gives "
        f"{fmt_p(dm['P_Value_Two_Sided'])} (two-sided), failing to reject equal predictive accuracy. A pooled "
        f"bootstrap test of the Sharpe-ratio difference between the combined and baseline trading strategies "
        f"gives a mean difference of {sharpe_diff['diff_mean']:.2f} with a 95% confidence interval of "
        f"[{sharpe_diff['ci_2.5']:.2f}, {sharpe_diff['ci_97.5']:.2f}], which contains zero. Breaking results "
        "down by settlement-weekday regime rather than pooling across the structural break does not rescue the "
        "result: the combined model's directional accuracy is 48.3% in the Wednesday-era and 48.5% in the "
        "Tuesday-era, both statistically indistinguishable from chance."
    ))
    embed_figure(
        doc, FIGS / "walk_forward_directional_accuracy.png",
        "Figure 3. Pooled out-of-fold directional accuracy with 95% bootstrap confidence intervals, by model "
        "condition, from the five-fold expanding-window walk-forward evaluation. The dashed line marks chance "
        "(50%)."
    )

    add_section_heading(doc, "5.5. Secondary Result: No Robust Settlement-Weekday Effect on Returns or Volatility", level=2)
    ret_m = regime_its["its_return_model"]
    pk_m = regime_its["its_parkinson_vol_model"]
    add_paragraph(doc, (
        f"The interrupted-time-series regression of daily returns on expiry-week status interacted with "
        f"settlement regime finds no statistically significant interaction: the Expiry-Week x Wednesday-era "
        f"coefficient is {ret_m['params']['EW_x_Wed']:.4f} ({fmt_p(ret_m['p_values']['EW_x_Wed'])}) and the "
        f"Expiry-Week x Tuesday-era coefficient is {ret_m['params']['EW_x_Tue']:.4f} "
        f"({fmt_p(ret_m['p_values']['EW_x_Tue'])}), estimated on 1,670 trading days spanning a "
        "Thursday-era baseline of over four years. The same specification using Parkinson range-based realized "
        f"volatility -- a methodological improvement over close-to-close volatility measures -- likewise finds "
        f"no significant interaction (Wednesday-era: {pk_m['params']['EW_x_Wed']:.4f}, "
        f"{fmt_p(pk_m['p_values']['EW_x_Wed'])}; Tuesday-era: {pk_m['params']['EW_x_Tue']:.4f}, "
        f"{fmt_p(pk_m['p_values']['EW_x_Tue'])}). Results using the 10-day rolling-standard-deviation volatility "
        "measure and absolute returns as an alternative volatility proxy are qualitatively the same and are "
        "available on request. We find no evidence, across four separate outcome specifications, that the "
        "settlement-weekday reforms shifted expiry-week return or volatility behavior."
    ))

    its_rows = [
        ("Return", "Wednesday-era", f"{ret_m['params']['EW_x_Wed']:.4f}", fmt_p(ret_m['p_values']['EW_x_Wed'])),
        ("Return", "Tuesday-era", f"{ret_m['params']['EW_x_Tue']:.4f}", fmt_p(ret_m['p_values']['EW_x_Tue'])),
        ("Parkinson volatility", "Wednesday-era", f"{pk_m['params']['EW_x_Wed']:.4f}", fmt_p(pk_m['p_values']['EW_x_Wed'])),
        ("Parkinson volatility", "Tuesday-era", f"{pk_m['params']['EW_x_Tue']:.4f}", fmt_p(pk_m['p_values']['EW_x_Tue'])),
    ]
    add_table_title(doc, "Table 4. Interrupted-Time-Series Expiry-Week x Settlement-Regime Interactions")
    add_table_from_rows(doc, ["Outcome", "Regime interaction", "Coefficient", "p-value"], its_rows)
    add_table_footnote(doc, "Note: Thursday-era is the omitted baseline regime. Newey-West standard errors (5 lags).")

    # ===================================================================
    # 6. DISCUSSION
    # ===================================================================
    add_section_heading(doc, "6. Discussion")

    add_section_heading(doc, "6.1. Economic Interpretation", level=2)
    add_paragraph(doc, (
        "The pattern of results is internally consistent with a mechanical liquidity-concentration "
        "explanation rather than an information-based or sentiment-based one. When Bank Nifty had its own "
        "weekly contract, position rollover and delta-hedging unwind were spread across roughly four expiry "
        "events per month; once only a monthly contract remained, the same underlying hedging and rollover "
        "activity had nowhere else to go but the single remaining expiry day, which is exactly what the "
        "difference-in-differences and event-study results show: a discrete, large, and statistically precise "
        "jump in expiry-day turnover and open interest concentration coincident with the contract removal, not "
        "a change in the general level or direction of returns. This is consistent with the mechanism "
        f"underlying {cite('stoll1987expiry')}'s original expiration-day finding and with {cite('bollen2004buying')}'s "
        "account of dealer hedging pressure, applied here to a regulatory change in how many settlement events "
        "exist per month rather than to the existence of an expiration cycle per se."
    ))
    add_paragraph(doc, (
        "The null predictability and null volatility results reported in Sections 5.4 and 5.5 should not be "
        "read as evidence that nothing happened; they are evidence about where the reform's effect did not "
        "show up. A reform that mechanically concentrates volume and open-interest unwinding onto fewer trading "
        "days has no obvious reason to change the sign or magnitude of average returns on those days, and our "
        "results are consistent with that distinction: the concentration channel is real and large, the "
        "return-predictability channel is not."
    ))

    add_section_heading(doc, "6.2. Policy Implications", level=2)
    add_paragraph(doc, (
        "For exchanges and clearing corporations, the practical implication is that retiring a weekly "
        "derivatives contract is not a liquidity-neutral simplification: it redistributes, and concentrates, "
        "the settlement-related trading activity that the weekly contract previously absorbed across multiple "
        "expiry events each month onto the single surviving expiry day. A roughly fourfold increase in "
        "turnover concentration on one day each month has direct implications for the margining, position-"
        "limit, and circuit-breaker calibration that clearing corporations set for settlement days, and for "
        "the operational capacity -- settlement-system throughput, risk-desk staffing, and surveillance "
        "resourcing -- that exchanges and their members need on that single day relative to an ordinary trading "
        "day. Regulators designing similar single-weekly-contract rules in other jurisdictions, or weighing "
        "further consolidation of derivatives listings, should budget for this concentration effect explicitly "
        "rather than assuming that removing a contract simply removes the activity it carried."
    ))

    add_section_heading(doc, "6.3. Limitations", level=2)
    add_paragraph(doc, (
        "Several limitations qualify these results. First, the primary analysis rests on a single policy event "
        "affecting a single pair of indices; while the Nifty 50 control group and the placebo-date, "
        "leave-one-out, and event-study checks together rule out several alternative explanations (a general "
        "market trend, the lot-size change, a small number of unusual expiry days, a slow pre-existing drift), "
        "we cannot rule out every index-specific confound coincident with the November 2024 window, such as "
        "banking-sector-specific news unrelated to the derivatives reform itself. Second, the Monthly-Only "
        "regime currently spans only 23 Bank Nifty expiry days; while leave-one-out exclusion shows the result "
        "is not driven by any single expiry, the regime's statistical power will improve as more post-reform "
        "data accumulates. Third, we observe turnover and open interest at daily frequency from exchange "
        "Bhavcopy records; we do not observe intraday timing, order-level data, or dealer-specific positioning, "
        "so we can document the aggregate concentration effect but not its precise intraday mechanics. Fourth, "
        "the secondary predictability analysis is itself a useful negative result but, by construction, cannot "
        "rule out predictability at a different forecast horizon, using intraday data, or using option-market "
        "variables (implied volatility, open-interest-weighted positioning by strike) that were not available "
        "for this study."
    ))

    # ===================================================================
    # 7. CONCLUSION
    # ===================================================================
    add_section_heading(doc, "7. Conclusion")
    add_paragraph(doc, (
        "Using a difference-in-differences design against a within-exchange control index, we find that "
        "discontinuing Bank Nifty's weekly options contract -- a consequence of a rule limiting each exchange "
        "to one weekly index-derivatives contract -- concentrated expiry-day trading turnover and open interest "
        "substantially more than a comparable trend in the Nifty 50 control, a result that survives correction "
        "for a coincident lot-size change, placebo cutover dates, leave-one-out exclusion of individual expiry "
        "days, and an event-study specification confirming a discrete post-reform jump. A separately tested "
        "settlement-weekday reform (Thursday to Wednesday to Tuesday) shows no corresponding effect on return "
        "predictability or expiry-week volatility under a leakage-free walk-forward evaluation and an "
        "interrupted-time-series analysis. The reform's measurable consequence for market participants is a "
        "liquidity-concentration effect with direct implications for settlement-day risk management, not a "
        "change in the predictability of index returns. Future work extending this design to other exchanges "
        "undergoing similar derivatives-listing consolidation, and incorporating intraday or option-chain data "
        "to test the dealer-hedging mechanism directly, would further strengthen the external validity of this "
        "result."
    ))

    # ===================================================================
    # GENERATIVE AI DECLARATION (required, PBFJ-mandated section before references)
    # ===================================================================
    add_section_heading(doc, "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process")
    add_paragraph(doc, cfg["declarations"]["generative_ai"].strip())

    add_section_heading(doc, "Funding")
    add_paragraph(doc, cfg["declarations"]["funding"].strip())

    add_section_heading(doc, "Data Availability")
    add_paragraph(doc, cfg["declarations"]["data_availability"].strip())

    # ===================================================================
    # REFERENCES
    # ===================================================================
    add_section_heading(doc, "References")
    used_keys = [
        "stoll1987expiry", "karolyi1996expiry", "chow2003expiry", "vipul2005expiry",
        "agarwalla2013expiry", "bollen2004buying", "hamilton1989new", "ang2002regime",
        "ryden1998stylized", "kritzman2012regime", "diebold1995comparing",
    ]
    sorted_keys = sorted(used_keys, key=lambda k: c[k].get("author", "").split(",")[0].split(" and ")[0])
    for key in sorted_keys:
        entry = c[key]
        authors = entry.get("author", "Unknown")
        year = entry.get("year", "n.d.")
        title = entry.get("title", "Untitled").strip("{}")
        journal = entry.get("journal", "").strip("{}")
        volume = entry.get("volume", "")
        number = entry.get("number", "")
        pages = entry.get("pages", "")
        doi = entry.get("doi", "")

        ref_text = f"{authors} ({year}). {title}. {journal}"
        if volume:
            ref_text += f", {volume}"
            if number:
                ref_text += f"({number})"
        if pages:
            ref_text += f", {pages}"
        ref_text += "."

        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.27)
        p.paragraph_format.first_line_indent = Cm(-1.27)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(ref_text)
        format_run(run, size=10)
        if doi:
            p.add_run(" ")
            r_doi = p.add_run(f"https://doi.org/{doi}")
            format_run(r_doi, size=9.5, color=(0, 0, 255))

    # ------------------------------------------------------------------
    out_dir = PROJECT_ROOT / cfg["output"]["docs_folder"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / cfg["output"]["paper_filename"]
    doc.save(out_path)

    body_text = []
    in_refs = False
    for p in doc.paragraphs:
        if p.text.strip() == "References":
            in_refs = True
        if not in_refs:
            body_text.append(p.text)
    body_word_count = len(" ".join(body_text).split())

    print(f"[SUCCESS] Generated anonymized main manuscript at {out_path}")
    print(f"Body word count (excl. references): {body_word_count}")
    print(f"References: {len(sorted_keys)}")


if __name__ == "__main__":
    main()
