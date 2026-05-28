"""Path handling, overwrite logic, and logging setup."""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(verbose: bool = False) -> None:
    fmt = "[%(asctime)s] %(levelname)s %(message)s"
    datefmt = "%H:%M:%S"
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root = logging.getLogger("pdf2md")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def resolve_output_path(pdf_path: Path) -> Path:
    return pdf_path.with_suffix(".md")


def collect_pdfs(path: Path | None) -> list[Path]:
    """Return list of PDF files to process."""
    if path is not None and path.is_file():
        return [path]
    directory = path if path is not None else Path.cwd()
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.pdf"))


def should_skip(output_path: Path, force: bool) -> bool:
    if output_path.exists() and not force:
        return True
    return False


def write_output(output_path: Path, content: str) -> None:
    output_path.write_text(content, encoding="utf-8", newline="\n")
