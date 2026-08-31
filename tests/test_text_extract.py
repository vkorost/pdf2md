"""Tests for text extraction path."""
import pymupdf4llm

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


def test_recovers_when_markdown_drops_most_text(tmp_path, monkeypatch):
    """A short but non-empty markdown result must not be trusted.

    Reproduces PDFs whose every text line sits inside an image bounding box:
    without its layout engine pymupdf4llm skips those lines and returns a
    plausible-looking document containing almost none of the page text.
    """
    lines = [f"sentence number {i} with real content" for i in range(30)]
    pdf = make_text_pdf(lines, tmp_path)

    monkeypatch.setattr(
        pymupdf4llm, "to_markdown", lambda *a, **kw: "# Title only\n", raising=True
    )

    md = extract_text(pdf)
    assert "sentence number 0 " in md
    assert "sentence number 29" in md


def test_keeps_markdown_when_coverage_is_good(tmp_path, monkeypatch):
    pdf = make_text_pdf(["alpha beta gamma delta epsilon"], tmp_path)

    monkeypatch.setattr(
        pymupdf4llm,
        "to_markdown",
        lambda *a, **kw: "## alpha beta gamma delta epsilon\n",
        raising=True,
    )

    md = extract_text(pdf)
    assert md.startswith("## alpha")


def test_layout_off_skips_the_coverage_check(tmp_path, monkeypatch):
    """`layout='off'` is documented as doing no verification at all."""
    lines = [f"sentence number {i} with real content" for i in range(30)]
    pdf = make_text_pdf(lines, tmp_path)

    monkeypatch.setattr(
        pymupdf4llm, "to_markdown", lambda *a, **kw: "# Title only\n", raising=True
    )

    md = extract_text(pdf, layout="off")
    assert md.strip() == "# Title only"
