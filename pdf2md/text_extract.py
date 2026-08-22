"""Text extraction path using pymupdf4llm."""
from __future__ import annotations

import logging
from pathlib import Path

import fitz
import pymupdf4llm

from pdf2md.layout import detect_column_collapse, extract_layout_text
from pdf2md.postprocess import clean_markdown

log = logging.getLogger("pdf2md")


def extract_text(
    pdf_path: Path | str,
    pages: list[int] | None = None,
    layout: str = "auto",
) -> str:
    """Extract Markdown from a text-based PDF.

    ``layout`` controls how column structure is handled:

    ``auto`` (default)
        Use pymupdf4llm, then verify that no column gaps were collapsed. If
        any were, re-extract with the geometry-aware layout path. This keeps
        pymupdf4llm's nicer prose output for ordinary documents while
        refusing to emit ambiguous text for tabular ones.
    ``preserve``
        Always use the geometry-aware layout path.
    ``off``
        Always use pymupdf4llm, with no verification. Faster, and matches the
        pre-fix behaviour, but can silently glue table cells together.

    Falls back to raw PyMuPDF text extraction if pymupdf4llm returns empty
    (can happen with certain PDF structures).
    """
    log.debug("Text extraction: %s (pages=%s, layout=%s)", pdf_path, pages, layout)

    if layout == "preserve":
        text = extract_layout_text(pdf_path, pages=pages)
        if text.strip():
            return clean_markdown(text)
        return _raw_fallback(pdf_path, pages)

    md = pymupdf4llm.to_markdown(str(pdf_path), pages=pages)

    if md.strip():
        if layout == "auto":
            collapsed = detect_column_collapse(pdf_path, md, pages=pages)
            if collapsed:
                log.warning(
                    "%s: %d row(s) had their column gaps collapsed by pymupdf4llm "
                    "(e.g. %r); re-extracting with layout preservation.",
                    Path(pdf_path).name,
                    len(collapsed),
                    "".join(collapsed[0][1])[:60],
                )
                layout_text = extract_layout_text(pdf_path, pages=pages)
                if layout_text.strip():
                    return clean_markdown(layout_text)
                log.warning(
                    "%s: layout re-extraction produced no text; keeping the "
                    "pymupdf4llm output, which may contain glued table cells.",
                    Path(pdf_path).name,
                )
        return clean_markdown(md)

    # Fallback: raw text extraction
    log.debug("pymupdf4llm returned empty, falling back to raw extraction")
    return _raw_fallback(pdf_path, pages)


def _raw_fallback(pdf_path: Path | str, pages: list[int] | None) -> str:
    """Last-resort extraction straight from PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    try:
        parts: list[str] = []
        page_indices = pages if pages is not None else range(len(doc))
        for i in page_indices:
            text = doc[i].get_text().strip()
            if text:
                parts.append(text)
    finally:
        doc.close()
    return clean_markdown("\n\n".join(parts)) if parts else "\n"
