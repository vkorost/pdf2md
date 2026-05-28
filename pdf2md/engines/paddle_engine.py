"""PaddleOCR engine."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import fitz

from pdf2md.postprocess import clean_markdown

log = logging.getLogger("pdf2md")


class PaddleEngine:
    name = "paddle"

    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "PaddleOCR engine requires paddleocr and paddlepaddle. "
                "Install with: pip install pdf2md[paddle]\n"
                "Note: first run downloads models to %USERPROFILE%\\.paddleocr"
            ) from exc
        self._ocr = None  # lazy init

    def _get_ocr(self, lang: str):
        from paddleocr import PaddleOCR
        # Map lang codes: "rus+eng" -> use "ru" for PaddleOCR
        paddle_lang = "ru" if "rus" in lang else "en"
        if self._ocr is None:
            self._ocr = PaddleOCR(use_angle_cls=True, lang=paddle_lang)
        return self._ocr

    def ocr_pdf(self, pdf_path: Path, lang: str) -> str:
        log.debug("PaddleOCR on %s (lang=%s)", pdf_path, lang)
        doc = fitz.open(str(pdf_path))
        pages_md: list[str] = []

        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            page_md = self._ocr_single_image(img_bytes, lang, i)
            pages_md.append(page_md)

        doc.close()
        return clean_markdown("\n\n---\n\n".join(pages_md))

    def ocr_image(self, image_bytes: bytes, lang: str) -> str:
        return self._ocr_single_image(image_bytes, lang, 0)

    def _ocr_single_image(self, image_bytes: bytes, lang: str, page_idx: int) -> str:
        ocr = self._get_ocr(lang)
        # PaddleOCR expects a file path or numpy array
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)

        try:
            result = ocr.ocr(str(tmp_path), cls=True)
            lines: list[str] = []
            if result and result[0]:
                for line_info in result[0]:
                    text = line_info[1][0] if isinstance(line_info[1], (list, tuple)) else str(line_info[1])
                    lines.append(text)
            return "\n".join(lines)
        finally:
            tmp_path.unlink(missing_ok=True)
