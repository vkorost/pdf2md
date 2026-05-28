"""Classify PDF pages as text or image (scanned)."""
from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

log = logging.getLogger("pdf2md")

PageClassification = list[tuple[int, str]]  # [(page_index, "text"|"image"), ...]


def classify_pages(pdf_path: Path | str) -> PageClassification:
    """Return per-page classification of text vs image."""
    doc = fitz.open(str(pdf_path))
    results: PageClassification = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        char_count = len(text)
        kind = "text" if char_count >= 50 else "image"
        results.append((i, kind))
        log.debug("Page %d: %d chars -> %s", i + 1, char_count, kind)
    doc.close()
    return results


def route_decision(classifications: PageClassification) -> str:
    """Return 'text', 'ocr', or 'mixed' based on page classifications."""
    if not classifications:
        return "ocr"

    image_pages = sum(1 for _, k in classifications if k == "image")
    total_pages = len(classifications)

    if total_pages == 0:
        return "ocr"

    image_ratio = image_pages / total_pages

    # All text
    if image_pages == 0:
        return "text"

    # All image
    text_pages = total_pages - image_pages
    if text_pages == 0:
        return "ocr"

    # More than 60% image pages -> OCR
    if image_ratio > 0.6:
        return "ocr"

    # Very few image pages (<10%) — treat as text, skip the image pages
    # rather than spending minutes OCR'ing 1-2 pages
    if image_ratio < 0.1:
        log.debug("Only %.0f%% image pages — treating as text (skipping image pages)", image_ratio * 100)
        return "text"

    # Mixed
    return "mixed"


def classify_pdf(pdf_path: Path | str) -> tuple[str, PageClassification]:
    """Classify a PDF and return (route, page_classifications).

    Also applies the total-chars-across-all-pages < 100 rule.
    """
    doc = fitz.open(str(pdf_path))
    total_chars = 0
    classifications: PageClassification = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        char_count = len(text)
        total_chars += char_count
        kind = "text" if char_count >= 50 else "image"
        classifications.append((i, kind))
        log.debug("Page %d: %d chars -> %s", i + 1, char_count, kind)
    doc.close()

    # Total chars across all pages < 100 -> OCR
    if total_chars < 100:
        log.debug("Total chars %d < 100 -> forcing OCR route", total_chars)
        return "ocr", [(i, "image") for i, _ in classifications]

    route = route_decision(classifications)
    log.debug("Route decision: %s (total_chars=%d)", route, total_chars)
    return route, classifications
