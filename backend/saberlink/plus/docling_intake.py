"""[PLUS] PDF-as-temporary-need intake, via Docling.

A user-uploaded PDF is parsed and turned into a raw_text_profile dict shaped
exactly like NEED's text_fields (see schema.ENTITY_SPECS["NEED"]) — the same
`pipeline.run_query(raw_text_profile=...)` path already used by the núcleo,
so this file adds zero new code to pipeline.py. The extracted profile is
NEVER written to institutional_needs.csv or entities.parquet: pipeline.py
builds an ephemeral row from it in memory, tags it official=False, and
discards it after the call.

Strictly additive: no non-plus module imports from here.
"""

from __future__ import annotations

from pathlib import Path


def _split_title_and_body(markdown_text: str, fallback_title: str) -> tuple[str, str]:
    lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    title = fallback_title
    body_lines = lines
    for i, line in enumerate(lines):
        if line.startswith("#"):
            title = line.lstrip("#").strip() or fallback_title
            body_lines = lines[i + 1 :]
            break
    body = " ".join(l.lstrip("#").strip() for l in body_lines)
    return title, body


def pdf_to_temp_need(path: str | Path, description_chars: int = 1200) -> dict:
    """Parses a PDF via Docling and returns a dict with NEED's text fields
    (title, description, context, expected_impact) populated from its
    content. `context`/`expected_impact` are left None (marked
    not_available downstream) when the document doesn't clearly separate
    that content — never fabricated."""
    from docling.document_converter import DocumentConverter

    path = Path(path)
    result = DocumentConverter().convert(str(path))
    markdown_text = result.document.export_to_markdown()

    title, body = _split_title_and_body(markdown_text, fallback_title=path.stem)
    description = body[:description_chars].strip()

    return {
        "title": title,
        "description": description or None,
        "context": None,
        "expected_impact": None,
        "_source_file_name": path.name,
    }


if __name__ == "__main__":
    import json
    import sys

    pdf_path = sys.argv[1]
    profile = pdf_to_temp_need(pdf_path)
    print(json.dumps(profile, ensure_ascii=False, indent=2))
