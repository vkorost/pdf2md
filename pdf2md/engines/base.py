"""Base protocol for OCR engines."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class OcrEngine(Protocol):
    name: str

    def ocr_pdf(self, pdf_path: Path, lang: str) -> str:
        """Run OCR on a full PDF, return Markdown string."""
        ...

    def ocr_image(self, image_bytes: bytes, lang: str) -> str:
        """Run OCR on a single page image (PNG bytes), return Markdown string."""
        ...
