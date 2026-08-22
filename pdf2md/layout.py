"""Geometry-aware text extraction and column-collapse detection.

Many PDFs — lab reports, invoices, bank statements, anything with a tabular
body — position columns using absolute coordinates rather than whitespace
characters. Markdown converters that concatenate the text spans of a row
without consulting their x-coordinates silently glue the cells together::

    CHLORIDE  |  102  |  98-110 mmol/L     ->    CHLORIDE10298-110 mmol/L

The result is not merely ugly, it is ambiguous: the reader cannot tell
whether the value was 102 or 1029. That is silent data corruption, and for
documents like lab reports it is worse than a hard failure.

This module provides:

``extract_layout_text``
    Re-inserts the inter-column whitespace by projecting each span's
    x-coordinate onto a monospace character grid, so column alignment (and
    therefore any meaning carried by column position) survives.

``detect_column_collapse``
    Flags rows whose wide column gaps were lost in some other extraction,
    so the caller can fall back or refuse to emit the corrupt output.
"""
from __future__ import annotations

import logging
from pathlib import Path

import fitz

log = logging.getLogger("pdf2md")

# A horizontal gap wider than this many points is a deliberate column
# boundary rather than ordinary inter-word spacing.
COLUMN_GAP_MIN = 8.0

# Spans whose tops fall within this many points belong to the same visual row.
ROW_TOLERANCE = 3.0

# Minimum length of a glued string before we treat it as evidence of
# collapse; shorter coincidences are not worth acting on.
MIN_GLUE_LEN = 8

DEFAULT_CHAR_WIDTH = 6.0


def _page_rows(page: fitz.Page) -> list[list[dict]]:
    """Group a page's non-empty spans into visual rows, left to right."""
    spans = [
        s
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        for s in line["spans"]
        if s["text"].strip()
    ]
    bands: dict[int, list[dict]] = {}
    for s in spans:
        bands.setdefault(round(s["bbox"][1] / ROW_TOLERANCE), []).append(s)
    return [sorted(bands[k], key=lambda s: s["bbox"][0]) for k in sorted(bands)]


def _median_char_width(rows: list[list[dict]]) -> float:
    """Estimate a representative character width for the page."""
    widths = [
        (s["bbox"][2] - s["bbox"][0]) / len(s["text"])
        for row in rows
        for s in row
        if len(s["text"]) > 1 and s["bbox"][2] > s["bbox"][0]
    ]
    if not widths:
        return DEFAULT_CHAR_WIDTH
    widths.sort()
    return max(widths[len(widths) // 2], 1.0)


def row_has_column_gap(row: list[dict]) -> bool:
    """True if `row` contains a gap wide enough to be a column boundary."""
    if len(row) < 2:
        return False
    return any(
        row[i + 1]["bbox"][0] - row[i]["bbox"][2] >= COLUMN_GAP_MIN
        for i in range(len(row) - 1)
    )


def extract_layout_text(pdf_path: Path | str, pages: list[int] | None = None) -> str:
    """Extract text preserving column structure.

    Each span is placed at the character column implied by its x-coordinate,
    so label / value / reference-range triplets stay separated and any meaning
    carried by column position is retained. Two spans are never concatenated
    without at least one space between them.
    """
    doc = fitz.open(str(pdf_path))
    try:
        indices = range(len(doc)) if pages is None else pages
        page_texts: list[str] = []
        for pno in indices:
            rows = _page_rows(doc[pno])
            char_w = _median_char_width(rows)
            lines: list[str] = []
            for row in rows:
                line = ""
                for s in row:
                    col = int(round(s["bbox"][0] / char_w))
                    if col > len(line):
                        line += " " * (col - len(line))
                    elif line and not line.endswith(" "):
                        # Never glue two spans together, even if the grid
                        # would place them adjacent.
                        line += " "
                    line += s["text"].strip()
                lines.append(line.rstrip())
            page_texts.append("\n".join(lines))
        return "\n\n".join(page_texts)
    finally:
        doc.close()


def detect_column_collapse(
    pdf_path: Path | str,
    extracted_text: str,
    pages: list[int] | None = None,
) -> list[tuple[int, list[str]]]:
    """Find rows whose column gaps were collapsed in ``extracted_text``.

    Returns ``[(page_number, [cell, ...]), ...]`` for every row that has a
    real column gap in the PDF but appears glued together in the extraction.
    A non-empty result means the text must not be trusted for tabular or
    numeric data.
    """
    doc = fitz.open(str(pdf_path))
    try:
        indices = range(len(doc)) if pages is None else pages
        collapsed: list[tuple[int, list[str]]] = []
        for pno in indices:
            for row in _page_rows(doc[pno]):
                if not row_has_column_gap(row):
                    continue
                cells = [s["text"].strip() for s in row]
                glued = "".join(cells)
                if len(glued) >= MIN_GLUE_LEN and glued in extracted_text:
                    collapsed.append((pno + 1, cells))
        return collapsed
    finally:
        doc.close()
