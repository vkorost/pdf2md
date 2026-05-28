"""Tests for PDF page classification and routing."""
from pathlib import Path

import fitz
import pytest

from pdf2md.router import classify_pages, classify_pdf, route_decision
from tests.conftest import make_text_pdf, make_image_pdf


class TestClassifyPages:
    def test_all_text_pages(self, tmp_path):
        pdf = make_text_pdf(["Hello world " * 20, "Another page " * 20], tmp_path)
        classifications = classify_pages(pdf)
        assert all(kind == "text" for _, kind in classifications)

    def test_all_image_pages(self, tmp_path):
        pdf = make_image_pdf(3, tmp_path)
        classifications = classify_pages(pdf)
        assert all(kind == "image" for _, kind in classifications)

    def test_mixed_pages(self, tmp_path):
        pdf = make_text_pdf(["Lots of text here " * 20, ""], tmp_path)
        classifications = classify_pages(pdf)
        assert classifications[0][1] == "text"
        assert classifications[1][1] == "image"


class TestRouteDecision:
    def test_all_text(self):
        assert route_decision([(0, "text"), (1, "text")]) == "text"

    def test_all_image(self):
        assert route_decision([(0, "image"), (1, "image")]) == "ocr"

    def test_mixed_minority_image(self):
        cls = [(i, "text") for i in range(4)] + [(4, "image")]
        assert route_decision(cls) == "mixed"

    def test_majority_image(self):
        cls = [(0, "text")] + [(i, "image") for i in range(1, 5)]
        assert route_decision(cls) == "ocr"

    def test_empty(self):
        assert route_decision([]) == "ocr"


class TestClassifyPdf:
    def test_total_chars_below_threshold(self, tmp_path):
        pdf = make_text_pdf(["Hi", "Ok"], tmp_path)
        route, cls = classify_pdf(pdf)
        assert route == "ocr"
        assert all(kind == "image" for _, kind in cls)

    def test_text_pdf_routes_text(self, tmp_path):
        pdf = make_text_pdf(["Hello world " * 50], tmp_path)
        route, cls = classify_pdf(pdf)
        assert route == "text"
