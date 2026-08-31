"""Text extraction path using pymupdf4llm."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import fitz
import pymupdf4llm

from pdf2md.layout import detect_column_collapse, extract_layout_text
from pdf2md.postprocess import clean_markdown

log = logging.getLogger("pdf2md")

# pymupdf4llm selects its extraction engine at import time. With its ML layout
# engine unavailable it degrades to a heuristic that skips every text line whose
# bounding box falls inside an image rect. PDFs that render each paragraph over
# a full-width raster then come back nearly empty -- non-empty, so the "did it
# return anything?" check below passes, but almost all of the text is gone.
# Compare against the raw PyMuPDF character count and refuse anything this lossy.
COVERAGE_THRESHOLD = 0.60

_WORD_CHAR_RE = re.compile(r"\w", re.UNICODE)


def layout_engine_available() -> bool:
    """True if pymupdf4llm is using its ML layout engine.

    The engine needs ``pymupdf.layout``, which in turn needs ``onnxruntime``.
    Without it extraction silently degrades on image-backed PDFs.
    """
    return bool(getattr(pymupdf4llm, "_use_layout", False))


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

    Under ``auto`` the markdown is also checked against the raw PyMuPDF
    character count, and re-extracted if pymupdf4llm dropped most of the text.

    Falls back to raw PyMuPDF text extraction if pymupdf4llm returns empty
    (can happen with certain PDF structures).
    """
    log.debug(
        "Text extraction: %s (pages=%s, layout=%s, layout_engine=%s)",
        pdf_path,
        pages,
        layout,
        "on" if layout_engine_available() else "off (onnxruntime missing)",
    )

    if layout == "preserve":
        text = extract_layout_text(pdf_path, pages=pages)
        if text.strip():
            return clean_markdown(text)
        return _raw_fallback(pdf_path, pages)

    md = pymupdf4llm.to_markdown(str(pdf_path), pages=pages)

    if layout == "auto":
        raw_chars = _word_chars(_raw_text(pdf_path, pages))
        if not _covers_page_text(md, raw_chars, pdf_path, "pymupdf4llm"):
            md = _recover_dropped_text(pdf_path, pages, raw_chars)

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


def _word_chars(text: str) -> int:
    """Count word characters, ignoring markdown punctuation and whitespace."""
    return len(_WORD_CHAR_RE.findall(text))


def _raw_text(pdf_path: Path | str, pages: list[int] | None) -> str:
    """Plain page text via PyMuPDF, used as the yardstick for coverage."""
    doc = fitz.open(str(pdf_path))
    try:
        page_indices = pages if pages is not None else range(len(doc))
        return "\n".join(doc[i].get_text().strip() for i in page_indices)
    finally:
        doc.close()


def _covers_page_text(
    md: str, raw_chars: int, pdf_path: Path | str, label: str
) -> bool:
    """True if `md` retained enough of the PDF's `raw_chars` to be trusted."""
    if not md.strip():
        return False
    if raw_chars == 0:
        return True
    md_chars = _word_chars(md)
    coverage = md_chars / raw_chars
    if coverage < COVERAGE_THRESHOLD:
        log.warning(
            "%s: %s recovered only %.0f%% of the page text (%d of %d chars); "
            "re-extracting.",
            Path(pdf_path).name,
            label,
            coverage * 100,
            md_chars,
            raw_chars,
        )
        return False
    log.debug("%s coverage %.0f%% (%d of %d chars)", label, coverage * 100, md_chars, raw_chars)
    return True


def _recover_dropped_text(
    pdf_path: Path | str, pages: list[int] | None, raw_chars: int
) -> str:
    """Re-extract a PDF whose markdown lost most of its text.

    Tries pymupdf4llm again with image regions ignored -- the usual cause is
    text lines being attributed to an image -- then the geometry-aware layout
    path, then raw PyMuPDF text.
    """
    try:
        md = pymupdf4llm.to_markdown(str(pdf_path), pages=pages, ignore_images=True)
    except TypeError:  # pymupdf4llm without the keyword
        md = ""
    if _covers_page_text(md, raw_chars, pdf_path, "pymupdf4llm(ignore_images)"):
        return md

    layout_text = extract_layout_text(pdf_path, pages=pages)
    if _covers_page_text(layout_text, raw_chars, pdf_path, "layout extraction"):
        return layout_text

    log.warning(
        "%s: falling back to raw PyMuPDF text; markdown conversion recovered "
        "too little of the page text.",
        Path(pdf_path).name,
    )
    return _raw_text(pdf_path, pages)


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
