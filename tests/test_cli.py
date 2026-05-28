"""CLI integration tests."""
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import make_text_pdf


def _run_pdf2md(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pdf2md", *args],
        capture_output=True, text=True, cwd=cwd, timeout=60,
    )


class TestCLI:
    def test_help(self):
        result = _run_pdf2md("--help")
        assert result.returncode == 0
        assert "pdf2md" in result.stdout

    def test_missing_file(self):
        result = _run_pdf2md("nonexistent.pdf")
        assert result.returncode == 2

    def test_single_file(self, tmp_path):
        pdf = make_text_pdf(["Hello World test content " * 20], tmp_path)
        result = _run_pdf2md("--ocr", "never", str(pdf))
        assert result.returncode == 0, result.stderr
        md_path = pdf.with_suffix(".md")
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "Hello World" in content

    def test_skip_existing(self, tmp_path):
        pdf = make_text_pdf(["Hello World test content " * 20], tmp_path)
        md_path = pdf.with_suffix(".md")
        md_path.write_text("existing", encoding="utf-8")

        result = _run_pdf2md(str(pdf))
        assert result.returncode == 0
        assert md_path.read_text(encoding="utf-8") == "existing"

    def test_force_overwrite(self, tmp_path):
        pdf = make_text_pdf(["Hello World test content " * 20], tmp_path)
        md_path = pdf.with_suffix(".md")
        md_path.write_text("existing", encoding="utf-8")

        result = _run_pdf2md("--force", "--ocr", "never", str(pdf))
        assert result.returncode == 0, result.stderr
        assert md_path.read_text(encoding="utf-8") != "existing"

    def test_dry_run(self, tmp_path):
        pdf = make_text_pdf(["Hello World test content " * 20], tmp_path)
        result = _run_pdf2md("--dry-run", str(pdf))
        assert result.returncode == 0
        assert "CONVERT" in result.stdout
        assert not pdf.with_suffix(".md").exists()

    def test_batch_mode(self, tmp_path):
        make_text_pdf(["Hello World batch test " * 20], tmp_path, "a.pdf")
        make_text_pdf(["Another batch test doc " * 20], tmp_path, "b.pdf")
        result = _run_pdf2md("--dir", str(tmp_path), "--ocr", "never")
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "a.md").exists()
        assert (tmp_path / "b.md").exists()

    def test_ocr_never(self, tmp_path):
        pdf = make_text_pdf(["Test content " * 20], tmp_path)
        result = _run_pdf2md("--ocr", "never", str(pdf))
        assert result.returncode == 0
        assert pdf.with_suffix(".md").exists()
