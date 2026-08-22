"""Tests for column-preserving extraction and collapse detection.

These cover the failure mode where a row's cells are positioned by absolute
x-coordinate with no separating whitespace, and a naive extractor
concatenates them into an ambiguous string::

    CHLORIDE  102  98-110 mmol/L   ->   CHLORIDE10298-110 mmol/L
"""
import fitz

from pdf2md.layout import (
    COLUMN_GAP_MIN,
    detect_column_collapse,
    extract_layout_text,
    row_has_column_gap,
)
from pdf2md.text_extract import extract_text
from tests.conftest import make_columnar_pdf, make_text_pdf

LAB_ROWS = [
    ["GLUCOSE", "62", "65-99 mg/dL"],
    ["CHLORIDE", "102", "98-110 mmol/L"],
    ["CARBON DIOXIDE", "26", "20-32 mmol/L"],
    ["METHYLMALONIC ACID", "124", "55-335 nmol/L"],
]


def test_layout_extraction_keeps_cells_separate(tmp_path):
    pdf = make_columnar_pdf(LAB_ROWS, tmp_path, "lab.pdf")
    text = extract_layout_text(pdf)
    for label, value, ref in LAB_ROWS:
        assert f"{label}{value}" not in text, f"{label} glued to its value"
        assert value in text
        assert label in text


def test_layout_extraction_preserves_reading_order(tmp_path):
    pdf = make_columnar_pdf(LAB_ROWS, tmp_path, "order.pdf")
    text = extract_layout_text(pdf)
    for row in LAB_ROWS:
        line = next(ln for ln in text.splitlines() if row[0] in ln)
        # label, then value, then reference range, left to right
        assert line.index(row[0]) < line.index(row[1]) < line.index(row[2])


def test_ambiguous_value_is_recoverable(tmp_path):
    """The regression that motivated this module.

    Glued, ``CHLORIDE10298-110`` could be read as 102 or 1029. Separated,
    the value is unambiguous.
    """
    pdf = make_columnar_pdf([["CHLORIDE", "102", "98-110 mmol/L"]], tmp_path, "amb.pdf")
    text = extract_layout_text(pdf)
    line = next(ln for ln in text.splitlines() if "CHLORIDE" in ln)
    fields = line.split()
    assert "102" in fields
    assert "CHLORIDE10298-110" not in text


def test_detect_column_collapse_flags_glued_text(tmp_path):
    pdf = make_columnar_pdf(LAB_ROWS, tmp_path, "glued.pdf")
    glued = "".join("".join(row) for row in LAB_ROWS)
    collapsed = detect_column_collapse(pdf, glued)
    assert len(collapsed) == len(LAB_ROWS)


def test_detect_column_collapse_clean_on_good_text(tmp_path):
    pdf = make_columnar_pdf(LAB_ROWS, tmp_path, "clean.pdf")
    good = extract_layout_text(pdf)
    assert detect_column_collapse(pdf, good) == []


def test_detect_column_collapse_ignores_narrow_gaps(tmp_path):
    """Ordinary inter-word spacing must not be mistaken for a column."""
    pdf = make_columnar_pdf(
        [["ALPHA", "BETA", "GAMMA"]], tmp_path, "narrow.pdf",
        x_positions=(40.0, 75.0, 110.0),
    )
    doc = fitz.open(str(pdf))
    rows = [
        [s for b in doc[0].get_text("dict")["blocks"]
         for l in b.get("lines", []) for s in l["spans"] if s["text"].strip()]
    ]
    doc.close()
    gaps = [
        rows[0][i + 1]["bbox"][0] - rows[0][i]["bbox"][2]
        for i in range(len(rows[0]) - 1)
    ]
    assert min(gaps) < COLUMN_GAP_MIN


def test_row_has_column_gap_needs_two_cells(tmp_path):
    assert row_has_column_gap([]) is False
    assert row_has_column_gap([{"bbox": (0, 0, 10, 10), "text": "x"}]) is False


def test_extract_text_auto_recovers_columns(tmp_path):
    """End-to-end: the default path must not emit glued cells."""
    pdf = make_columnar_pdf(LAB_ROWS, tmp_path, "auto.pdf")
    md = extract_text(pdf)
    for label, value, _ in LAB_ROWS:
        assert f"{label}{value}" not in md
        assert value in md


def test_extract_text_layout_off_skips_verification(tmp_path):
    """`off` must still produce text; it simply does not verify."""
    pdf = make_columnar_pdf(LAB_ROWS, tmp_path, "off.pdf")
    md = extract_text(pdf, layout="off")
    assert md.strip()
    assert md.endswith("\n")


def test_extract_text_layout_preserve(tmp_path):
    pdf = make_columnar_pdf(LAB_ROWS, tmp_path, "preserve.pdf")
    md = extract_text(pdf, layout="preserve")
    assert "CHLORIDE102" not in md
    assert "102" in md
    assert md.endswith("\n")


def test_prose_pdf_unaffected_by_auto(tmp_path):
    """Ordinary prose must still go through the pymupdf4llm path unchanged."""
    pdf = make_text_pdf(["The quick brown fox jumps over the lazy dog."], tmp_path)
    md = extract_text(pdf)
    assert "quick brown fox" in md
    assert md.endswith("\n")
