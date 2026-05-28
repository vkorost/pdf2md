"""Tests for text extraction path."""
from pdf2md.text_extract import extract_text
from tests.conftest import make_text_pdf


def test_basic_extraction(tmp_path):
    pdf = make_text_pdf(["Hello World, this is a test document."], tmp_path)
    md = extract_text(pdf)
    assert "Hello World" in md
    assert md.endswith("\n")


def test_trailing_newline(tmp_path):
    pdf = make_text_pdf(["Some text content here."], tmp_path)
    md = extract_text(pdf)
    assert md.endswith("\n")
    assert not md.endswith("\n\n\n\n")
