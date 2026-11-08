"""
Generates docs/Title_Page.docx from manuscript/paper_config.yaml.

Mirrors the structure of the previous hand-authored title page but pulls
authors/affiliations/highlights live from config so it can never again drift
out of sync with the actual manuscript (the cause of the mismatched title
page found in sbe-submission-files, which named a different paper entirely).
"""
import argparse
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH


def add_heading(doc, text, size=13, bold=True, space_before=12, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    return p


def add_para(doc, text, size=11, bold=False, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    return p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="manuscript/paper_config.yaml")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / args.config
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    p = doc.add_paragraph()
    run = p.add_run("TITLE PAGE — FOR EDITOR USE ONLY (author information not included in the manuscript file)")
    run.font.name = 'Times New Roman'
    run.font.size = Pt(10)
    run.font.italic = True

    journal = cfg.get("journal", {})
    add_para(
        doc,
        f"Journal: {journal.get('name', '')}  |  {journal.get('quartile', '')}  |  ISSN: {journal.get('issn', '')}",
        size=10,
    )
    add_para(doc, f"Section: {journal.get('section', '')} → {journal.get('subsection', '')}", size=10)

    paper = cfg.get("paper", {})
    add_heading(doc, paper.get("title", "").strip(), size=14)
    if paper.get("short_title"):
        add_para(doc, f"Running title: {paper['short_title']} ({len(paper['short_title'])} characters)", size=10, italic=True)
    add_para(doc, f"Article Type: {paper.get('article_type', '')}", size=10, italic=True)

    authors = cfg.get("authors", [])
    affiliations = cfg.get("affiliations", {})
    aff_ids = sorted({a.get("affiliation_id") for a in authors if a.get("affiliation_id")})
    aff_index = {aid: i + 1 for i, aid in enumerate(aff_ids)}

    add_heading(doc, "Authors", size=12)
    author_line_parts = []
    for a in authors:
        marker = str(aff_index.get(a.get("affiliation_id"), ""))
        star = ",*" if a.get("corresponding") else ""
        author_line_parts.append(f"{a['name']} ({marker}{star})")
    add_para(doc, "; ".join(author_line_parts))

    add_heading(doc, "Affiliations", size=12)
    for aid in aff_ids:
        aff = affiliations.get(aid, {})
        idx = aff_index[aid]
        add_para(
            doc,
            f"({idx}) {aff.get('department', '')}, {aff.get('institution', '')}, "
            f"{aff.get('city', '')}, {aff.get('state', '')}, {aff.get('country', '')}",
        )

    corresponding = next((a for a in authors if a.get("corresponding")), authors[0] if authors else {})
    add_heading(doc, "Corresponding Author", size=12)
    add_para(doc, corresponding.get("name", ""))
    add_para(doc, f"Email: {corresponding.get('email', '')}")

    add_heading(doc, "ORCID iDs", size=12)
    for a in authors:
        orcid = a.get("orcid") or "to be added before submission"
        add_para(doc, f"{a['name']}: {orcid}")

    add_heading(doc, "Author Contributions (CRediT)", size=12)
    for a in authors:
        credit = ", ".join(a.get("credit", []))
        add_para(doc, f"{a['name']}: {credit}")

    add_heading(doc, "Acknowledgements", size=12)
    add_para(doc, cfg.get("acknowledgements", "").strip())

    decl = cfg.get("declarations", {})
    add_heading(doc, "Declarations", size=12)
    add_para(doc, f"Funding: {decl.get('funding', '').strip()}")
    add_para(doc, f"Conflict of Interest: {decl.get('conflict_of_interest', '').strip()}")
    add_para(doc, f"Data Availability: {decl.get('data_availability', '').strip()}")
    add_para(doc, f"Ethical Approval: {decl.get('ethical_approval', '').strip()}")

    add_heading(doc, "Keywords", size=12)
    add_para(doc, "; ".join(cfg.get("keywords", [])))

    highlights = cfg.get("highlights", [])
    if highlights:
        add_heading(doc, "Highlights", size=12)
        for h in highlights:
            add_para(doc, f"• {h}")

    out_dir = project_root / cfg.get("output", {}).get("docs_folder", "docs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / cfg.get("output", {}).get("title_page_filename", "Title_Page.docx")
    doc.save(out_path)
    print(f"[SUCCESS] Generated title page at {out_path}")


if __name__ == "__main__":
    main()
