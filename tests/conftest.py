"""Shared test utilities for creating synthetic PDFs."""
from __future__ import annotations

import tempfile
from pathlib import Path

import fitz


def make_text_pdf(pages_text: list[str], directory: Path | None = None, name: str | None = None) -> Path:
    """Create a PDF with given text per page."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=12)

    if directory and name:
        path = directory / name
    else:
        fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=directory)
        import os
        os.close(fd)
        path = Path(tmp_name)

    doc.save(str(path))
    doc.close()
    return path


def make_image_pdf(num_pages: int = 1, directory: Path | None = None) -> Path:
    """Create a PDF with blank image pages (no extractable text)."""
    doc = fitz.open()
    for _ in range(num_pages):
        page = doc.new_page()
        page.draw_rect(fitz.Rect(50, 50, 200, 200), color=(0.5, 0.5, 0.5), fill=(0.8, 0.8, 0.8))

    fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=directory)
    import os
    os.close(fd)
    path = Path(tmp_name)
    doc.save(str(path))
    doc.close()
    return path


def make_columnar_pdf(
    rows: list[list[str]],
    directory: Path | None = None,
    name: str | None = None,
    x_positions: tuple[float, ...] = (40.0, 240.0, 400.0),
    fontname: str = "Courier",
) -> Path:
    """Create a PDF whose columns are positioned by coordinate, not whitespace.

    This is the shape that breaks naive span concatenation: each cell is an
    independent text object at an absolute x, with no space characters
    between cells. Lab reports, invoices and bank statements all look like
    this. ``make_text_pdf`` cannot reproduce it because it writes a single
    text run per page.
    """
    doc = fitz.open()
    page = doc.new_page()
    y = 100.0
    for row in rows:
        for x, cell in zip(x_positions, row):
            if cell:
                page.insert_text((x, y), cell, fontsize=10, fontname=fontname)
        y += 20.0

    if directory and name:
        path = directory / name
    else:
        fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=directory)
        import os
        os.close(fd)
        path = Path(tmp_name)

    doc.save(str(path))
    doc.close()
    return path
