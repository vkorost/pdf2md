"""ocrmypdf OCR engine — uses ocrmypdf Python API with --sidecar."""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

import fitz

from pdf2md.postprocess import clean_markdown

log = logging.getLogger("pdf2md")

TESSERACT_WINDOWS_HINT = (
    "Tesseract not found on PATH. Install from: "
    "https://github.com/UB-Mannheim/tesseract/wiki"
)


def _find_tesseract() -> str | None:
    path = shutil.which("tesseract")
    if path:
        return path
    candidate = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if candidate.exists():
        return str(candidate)
    return None


class OcrmypdfEngine:
    name = "ocrmypdf"

    def __init__(self) -> None:
        try:
            import ocrmypdf  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "ocrmypdf engine requires ocrmypdf. "
                "Install with: pip install pdf2md[ocrmypdf]"
            ) from exc

        tess = _find_tesseract()
        if tess is None:
            raise RuntimeError(TESSERACT_WINDOWS_HINT)
        self._tesseract_path = tess
        # Add Tesseract directory to PATH so ocrmypdf finds it
        tess_dir = str(Path(tess).parent)
        if tess_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = tess_dir + os.pathsep + os.environ.get("PATH", "")

    def ocr_pdf(self, pdf_path: Path, lang: str) -> str:
        import ocrmypdf

        log.debug("ocrmypdf OCR on %s (lang=%s)", pdf_path, lang)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            sidecar = tmp / "sidecar.txt"
            output_pdf = tmp / "output.pdf"

            ocrmypdf.ocr(
                str(pdf_path),
                str(output_pdf),
                language=lang,
                sidecar=str(sidecar),
                force_ocr=True,
                progress_bar=False,
            )

            text = sidecar.read_text(encoding="utf-8")
            return clean_markdown(text)

    def ocr_image(self, image_bytes: bytes, lang: str) -> str:
        fd, tmp_name = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        tmp_path = Path(tmp_name)

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
