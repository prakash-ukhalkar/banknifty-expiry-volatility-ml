"""
Generates Highlights.docx -- PBFJ requires article highlights as a SEPARATE
editable file (filename must contain "highlights"), 3-5 bullets, each a
maximum of 85 characters including spaces.
"""
import argparse
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt, Cm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="manuscript/paper_config_pbfj.yaml")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / args.config
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    highlights = cfg.get("highlights", [])
    max_chars = cfg.get("journal", {}).get("highlights_max_chars", 85)
    if not (3 <= len(highlights) <= 5):
        raise ValueError(f"PBFJ requires 3-5 highlights, got {len(highlights)}")
    for h in highlights:
        if len(h) > max_chars:
            raise ValueError(f"Highlight exceeds {max_chars} characters ({len(h)}): {h}")

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    title_p = doc.add_paragraph()
    title_run = title_p.add_run(cfg["paper"]["title"].strip())
    title_run.font.name = "Times New Roman"
    title_run.font.size = Pt(12)
    title_run.font.bold = True

    heading_p = doc.add_paragraph()
    heading_run = heading_p.add_run("Highlights")
    heading_run.font.name = "Times New Roman"
    heading_run.font.size = Pt(12)
    heading_run.font.bold = True

    for h in highlights:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(h)
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)

    out_path = (
        Path(args.out) if args.out
        else project_root / cfg["output"]["docs_folder"] / cfg["output"].get("highlights_filename", "Highlights.docx")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    print(f"[SUCCESS] Generated highlights at {out_path}")


if __name__ == "__main__":
    main()
