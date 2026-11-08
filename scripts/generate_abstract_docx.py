"""Generates a standalone Abstract.docx from manuscript/paper_config.yaml."""
import argparse
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt, Cm


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

    title_p = doc.add_paragraph()
    title_run = title_p.add_run(cfg["paper"]["title"].strip().upper())
    title_run.font.name = 'Times New Roman'
    title_run.font.size = Pt(14)
    title_run.font.bold = True

    heading_p = doc.add_paragraph()
    heading_run = heading_p.add_run("Abstract")
    heading_run.font.name = 'Times New Roman'
    heading_run.font.size = Pt(12)
    heading_run.font.bold = True

    body_p = doc.add_paragraph()
    body_run = body_p.add_run(cfg["abstract"].strip().replace("\n", " "))
    body_run.font.name = 'Times New Roman'
    body_run.font.size = Pt(11)

    kw_p = doc.add_paragraph()
    kw_run = kw_p.add_run("Keywords: " + "; ".join(cfg.get("keywords", [])))
    kw_run.font.name = 'Times New Roman'
    kw_run.font.size = Pt(10)
    kw_run.font.italic = True

    out_path = Path(args.out) if args.out else project_root / cfg["output"]["docs_folder"] / "Abstract.docx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    print(f"[SUCCESS] Generated abstract at {out_path}")


if __name__ == "__main__":
    main()
