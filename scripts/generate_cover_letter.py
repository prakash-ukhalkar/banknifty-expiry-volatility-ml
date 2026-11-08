"""Generates a Cover_Letter.docx addressed to the configured target journal from paper_config.yaml."""
import argparse
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt, Cm


def add_para(doc, text, size=11, bold=False, italic=False, space_after=10):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    return p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="manuscript/paper_config.yaml")
    parser.add_argument("--out", default=None)
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

    authors = cfg.get("authors", [])
    corresponding = next((a for a in authors if a.get("corresponding")), authors[0] if authors else {})
    co_authors = [a for a in authors if not a.get("corresponding")]
    affiliations = cfg.get("affiliations", {})
    corr_aff = affiliations.get(corresponding.get("affiliation_id", ""), {})
    journal = cfg.get("journal", {})
    paper = cfg.get("paper", {})
    cl = cfg.get("cover_letter", {})

    add_para(doc, paper.get("submission_date", ""), size=10)
    add_para(doc, "To")
    add_para(doc, "The Editor-in-Chief")
    add_para(doc, f"{journal.get('name', '')}")
    add_para(doc, f"{journal.get('publisher', '')}", size=10, italic=True)

    add_para(
        doc,
        f"Subject: Submission of Manuscript: {paper.get('title', '').strip()}",
        bold=True,
    )

    add_para(doc, "Dear Editor-in-Chief,")

    add_para(
        doc,
        f"We are pleased to submit our manuscript titled \"{paper.get('title', '').strip()}\" for consideration "
        f"as a {paper.get('article_type', 'Research Article')} in {journal.get('name', '')}.",
    )

    for para in cl.get("key_results", []):
        pass  # rendered as bullets below after the intro paragraph

    intro2 = cl.get("journal_fit", "").strip()
    if intro2:
        add_para(doc, intro2)

    add_para(doc, "Key results of the study:", bold=True)
    for kr in cl.get("key_results", []):
        add_para(doc, f"•  {kr}", size=10.5)

    dataset_desc = cl.get("dataset_description", "").strip()
    if dataset_desc:
        add_para(doc, dataset_desc)

    add_para(
        doc,
        "We confirm that the manuscript is original, has not been published previously, is not under consideration "
        "elsewhere, and has been approved by all authors.",
    )
    add_para(
        doc,
        "Thank you for your time and consideration. We look forward to your response.",
    )

    add_para(doc, "Yours sincerely,")
    add_para(doc, corresponding.get("name", ""))
    add_para(doc, "Corresponding Author (on behalf of all co-authors)", size=10)
    add_para(
        doc,
        f"{corr_aff.get('department', '')}, {corr_aff.get('institution', '')}, "
        f"{corr_aff.get('city', '')}, {corr_aff.get('country', '')}",
        size=10,
    )
    add_para(doc, f"Email: {corresponding.get('email', '')}", size=10)

    if co_authors:
        add_para(doc, "Co-authors:", bold=True, size=10)
        for a in co_authors:
            aff = affiliations.get(a.get("affiliation_id", ""), {})
            add_para(
                doc,
                f"{a['name']}, {aff.get('institution', '')}, {aff.get('city', '')}, {aff.get('country', '')}",
                size=10,
            )

    out_path = Path(args.out) if args.out else project_root / cfg["output"]["docs_folder"] / cfg["output"].get("cover_letter_filename", "Cover_Letter.docx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    print(f"[SUCCESS] Generated cover letter at {out_path}")


if __name__ == "__main__":
    main()
