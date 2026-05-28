"""Core conversion logic: route and convert a single PDF."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import fitz

from pdf2md.engines import get_engine
from pdf2md.engines.base import OcrEngine
from pdf2md.postprocess import clean_markdown
from pdf2md.router import classify_pdf
from pdf2md.text_extract import extract_text

log = logging.getLogger("pdf2md")


def convert_pdf(
    pdf_path: Path,
    ocr_mode: str = "auto",
    engine_name: str = "marker",
    lang: str = "rus+eng",
) -> tuple[str, str]:
    """Convert a single PDF to Markdown.

    Returns (markdown_text, method_used) where method_used is one of:
    "text", "ocr-{engine}", "mixed-{engine}".
    """
    start = time.perf_counter()

    # Determine routing
    if ocr_mode == "force":
        route = "ocr"
        classifications = None
    elif ocr_mode == "never":
        route = "text"
        classifications = None
    else:  # auto
        route, classifications = classify_pdf(pdf_path)

    log.info("%s -> route: %s", pdf_path.name, route)

    if route == "text":
        md = extract_text(pdf_path)
        method = "text"
    elif route == "ocr":
        engine = get_engine(engine_name)
        md = engine.ocr_pdf(pdf_path, lang)
        method = f"ocr-{engine_name}"
    else:  # mixed
        engine = get_engine(engine_name)
        md = _convert_mixed(pdf_path, classifications, engine, lang)
        method = f"mixed-{engine_name}"

    elapsed = time.perf_counter() - start
    log.info("%s done in %.1fs via %s", pdf_path.name, elapsed, method)
    return md, method


def _convert_mixed(
    pdf_path: Path,
    classifications: list[tuple[int, str]],
    engine: OcrEngine,
    lang: str,
) -> str:
    """Handle mixed PDFs: text-extract text pages, OCR image pages."""
    parts: list[str] = []
    doc = fitz.open(str(pdf_path))

    for page_idx, kind in classifications:
        if kind == "text":
            try:
                page_md = extract_text(pdf_path, pages=[page_idx])
                parts.append(page_md)
            except Exception:
                log.exception("Text extraction failed on page %d", page_idx + 1)
                parts.append(f"> [Text extraction failed on page {page_idx + 1}]")
        else:  # image
            try:
                page = doc[page_idx]
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                page_md = engine.ocr_image(img_bytes, lang)
                parts.append(clean_markdown(page_md))
            except Exception:
                log.exception("OCR failed on page %d", page_idx + 1)
                parts.append(f"> [OCR failed on page {page_idx + 1}]")

    doc.close()
    return "\n\n---\n\n".join(parts) + "\n"
