"""Tests for OCR engines — skip if not installed."""
import pytest

from pdf2md.engines import get_engine
from tests.conftest import make_text_pdf


@pytest.mark.parametrize("engine_name", ["marker", "ocrmypdf", "paddle"])
def test_engine_loads(engine_name):
    try:
        engine = get_engine(engine_name)
        assert engine.name == engine_name
    except (ImportError, RuntimeError) as exc:
        pytest.skip(f"Engine {engine_name} not available: {exc}")


@pytest.mark.parametrize("engine_name", ["marker", "ocrmypdf", "paddle"])
def test_engine_ocr(engine_name, tmp_path):
    try:
        engine = get_engine(engine_name)
    except (ImportError, RuntimeError) as exc:
        pytest.skip(f"Engine {engine_name} not available: {exc}")

    pdf = make_text_pdf(["Test OCR content for engine validation"], tmp_path)
    result = engine.ocr_pdf(pdf, lang="eng")
    assert isinstance(result, str)
    assert len(result) > 0
