"""Detect OCR language from PDF filename."""
from __future__ import annotations

import re
from pathlib import Path

# Cyrillic Unicode range
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def detect_lang(pdf_path: Path) -> str:
    """Return OCR language code based on filename characters.

    If the filename contains Cyrillic characters -> 'rus+eng'
    Otherwise -> 'eng'
    """
    name = pdf_path.stem
    if _CYRILLIC_RE.search(name):
        return "rus+eng"
    return "eng"
