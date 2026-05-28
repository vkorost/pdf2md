"""Marker OCR engine."""
from __future__ import annotations

import logging
from pathlib import Path

from pdf2md.postprocess import clean_markdown

log = logging.getLogger("pdf2md")


class MarkerEngine:
    name = "marker"

    def __init__(self) -> None:
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
        except ImportError as exc:
            raise ImportError(
                "Marker engine requires marker-pdf. "
                "Install with: pip install pdf2md[marker]"
            ) from exc
        self._model_dict = create_model_dict()
        self._converter_cls = PdfConverter

    def ocr_pdf(self, pdf_path: Path, lang: str) -> str:
        log.debug("Marker OCR on %s (lang=%s)", pdf_path, lang)
        from marker.output import text_from_rendered

        converter = self._converter_cls(artifact_dict=self._model_dict)
        rendered = converter(str(pdf_path))
        md_text, _, _ = text_from_rendered(rendered)
        return clean_markdown(md_text)

    def ocr_image(self, image_bytes: bytes, lang: str) -> str:
        # Marker works on PDFs, not individual images directly.
        # For single-page OCR in mixed mode, we write a temp PDF.
        import tempfile
        import fitz

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        doc = fitz.open()
        img = fitz.open(stream=image_bytes, filetype="png")
        rect = img[0].rect
        page = doc.new_page(width=rect.width, height=rect.height)
        page.insert_image(rect, stream=image_bytes)
        doc.save(str(tmp_path))
        doc.close()
        img.close()

        try:
            return self.ocr_pdf(tmp_path, lang)
        finally:
            tmp_path.unlink(missing_ok=True)
