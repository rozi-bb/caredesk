"""Extract the selected F-tags from CMS Appendix PP into corpus/ftags/.

Keeps each tag's regulation text, intent, definitions, and guidance, and
drops the parts written for surveyors (procedures, noncompliance criteria,
deficiency categorization). See ADR-0005 for why only these tags.

Usage:
    uv run python scripts/extract_ftags.py [--pdf PATH]

The PDF is public domain and not committed. Download it from:
https://www.cms.gov/Regulations-and-Guidance/Guidance/Manuals/downloads/som107ap_pp_guidelines_ltcf.pdf
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = ROOT / "data" / "sources" / "som107ap_pp_guidelines_ltcf.pdf"
OUTPUT = ROOT / "corpus" / "ftags"

# Chosen from the example questions in docs/prd.md section 4.
TAGS = {
    "F550": "Resident Rights and Exercise of Rights",
    "F557": "Respect, Dignity, and Right to Personal Property",
    "F559": "Choose or Be Notified of Room or Roommate Change",
    "F561": "Self-Determination",
    "F563": "Right to Receive or Deny Visitors",
    "F567": "Protection and Management of Personal Funds",
    "F578": "Request, Refuse, or Discontinue Treatment; Advance Directives",
    "F580": "Notification of Changes",
    "F583": "Personal Privacy and Confidentiality of Records",
    "F585": "Grievances",
    "F600": "Free from Abuse and Neglect",
    "F604": "Right to be Free from Physical Restraints",
    "F609": "Reporting of Alleged Violations",
    "F700": "Bed Rails",
}
HEADING = re.compile(r"F\d{3}\s*")
SURVEYOR_SECTIONS = re.compile(
    r"^(PROCEDURES|PROBES|KEY ELEMENTS OF NONCOMPLIANCE|POTENTIAL TAGS FOR ADDITIONAL"
    r" INVESTIGATION|DEFICIENCY CATEGORIZATION)"
)


def tag_sections(lines: list[str]) -> dict[str, list[str]]:
    """Return the lines of each wanted tag, up to its first surveyor section."""
    heads = [i for i, line in enumerate(lines) if HEADING.fullmatch(line)]
    sections: dict[str, list[str]] = {}
    for position, start in enumerate(heads):
        tag = lines[start].strip()
        if tag not in TAGS or tag in sections:
            continue
        end = heads[position + 1] if position + 1 < len(heads) else len(lines)
        body = lines[start + 1 : end]
        cut = next(
            (i for i, line in enumerate(body) if SURVEYOR_SECTIONS.match(line)),
            len(body),
        )
        sections[tag] = body[:cut]
    return sections


def clean(lines: list[str]) -> str:
    """Strip trailing spaces and collapse runs of blank lines."""
    text = "\n".join(line.rstrip() for line in lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def main() -> None:
    """Read the PDF and write one Markdown file per tag."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    args = parser.parse_args()

    reader = PdfReader(args.pdf)
    lines = "\n".join(page.extract_text() or "" for page in reader.pages).split("\n")
    sections = tag_sections(lines)
    missing = sorted(set(TAGS) - set(sections))
    if missing:
        raise SystemExit(f"Tags not found in {args.pdf}: {', '.join(missing)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for tag, body in sections.items():
        revision = next(
            (line.strip() for line in body if line.strip().startswith("(Rev.")), ""
        )
        header = (
            f"# {tag} — {TAGS[tag]}\n\n"
            f"Source: CMS State Operations Manual, Appendix PP {revision}. Public domain.\n"
            "Surveyor procedures and deficiency criteria removed.\n\n"
        )
        (OUTPUT / f"{tag}.md").write_text(header + clean(body))
        print(f"{tag}: {len(body):5d} lines")
    print(f"Wrote {len(sections)} tags to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
