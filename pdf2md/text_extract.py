"""Text extraction path using pymupdf4llm."""
from __future__ import annotations

import logging
from pathlib import Path

import fitz
import pymupdf4llm

from pdf2md.postprocess import clean_markdown

log = logging.getLogger("pdf2md")


def extract_text(pdf_path: Path | str, pages: list[int] | None = None) -> str:
    """Extract Markdown from a text-based PDF using pymupdf4llm.

    Falls back to raw PyMuPDF text extraction if pymupdf4llm returns empty
    (can happen with certain PDF structures).
    """
    log.debug("Text extraction: %s (pages=%s)", pdf_path, pages)
    md = pymupdf4llm.to_markdown(str(pdf_path), pages=pages)
    if md.strip():
        return clean_markdown(md)

    # Fallback: raw text extraction
    log.debug("pymupdf4llm returned empty, falling back to raw extraction")
    doc = fitz.open(str(pdf_path))
    parts: list[str] = []
    page_indices = pages if pages is not None else range(len(doc))
    for i in page_indices:
        text = doc[i].get_text().strip()
        if text:
            parts.append(text)
    doc.close()
    return clean_markdown("\n\n".join(parts)) if parts else "\n"
