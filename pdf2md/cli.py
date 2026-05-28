"""CLI entry point for pdf2md."""
from __future__ import annotations

import argparse
import io
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Fix Windows console encoding for Cyrillic filenames
if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

from pdf2md.converter import convert_pdf
from pdf2md.io_utils import (
    collect_pdfs,
    resolve_output_path,
    setup_logging,
    should_skip,
    write_output,
)
from pdf2md.lang_detect import detect_lang

log = logging.getLogger("pdf2md")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf2md",
        description="Convert PDFs to Markdown with automatic text/OCR routing.",
    )
    p.add_argument(
        "file", nargs="?", type=Path, default=None,
        help="PDF file to convert. If omitted, converts all PDFs in the directory.",
    )
    p.add_argument(
        "--dir", type=Path, default=None,
        help="Directory containing PDFs to convert.",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Overwrite existing .md files.",
    )
    p.add_argument(
        "--ocr", choices=["auto", "force", "never"], default="auto",
        help="OCR mode: auto (detect), force (always OCR), never (text only).",
    )
    p.add_argument(
        "--engine", choices=["marker", "ocrmypdf", "paddle"], default="ocrmypdf",
        help="OCR engine to use.",
    )
    p.add_argument(
        "--lang", default="auto",
        help="OCR language codes (Tesseract format). 'auto' detects from filename: Cyrillic -> rus+eng, otherwise eng.",
    )
    p.add_argument(
        "--workers", type=int, default=1,
        help="Number of parallel workers for batch mode.",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Enable debug logging.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print planned actions without writing files.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    # Determine input files
    if args.file is not None:
        target = Path(args.file)
        if not target.exists():
            log.error("File not found: %s", target)
            sys.exit(2)
        if not target.is_file():
            log.error("Not a file: %s", target)
            sys.exit(2)
        pdfs = [target]
    elif args.dir is not None:
        if not args.dir.is_dir():
            log.error("Directory not found: %s", args.dir)
            sys.exit(2)
        pdfs = collect_pdfs(args.dir)
    else:
        pdfs = collect_pdfs(None)

    if not pdfs:
        log.error("No PDF files found.")
        sys.exit(2)

    log.info("Found %d PDF(s) to process.", len(pdfs))

    if args.dry_run:
        for pdf in pdfs:
            out = resolve_output_path(pdf)
            skip = should_skip(out, args.force)
            lang = detect_lang(pdf) if args.lang == "auto" else args.lang
            action = "SKIP (exists)" if skip else "CONVERT"
            print(f"  {action}: {pdf.name} -> {out.name} [lang={lang}]")
        return

    # Process files
    failures = 0
    total = len(pdfs)

    if args.workers > 1 and total > 1:
        failures = _process_parallel(pdfs, args, total)
    else:
        failures = _process_sequential(pdfs, args, total)

    if failures > 0:
        if failures == total:
            log.error("All %d file(s) failed.", total)
            sys.exit(2)
        else:
            log.warning("%d of %d file(s) failed.", failures, total)
            sys.exit(1)


def _process_sequential(pdfs: list[Path], args, total: int) -> int:
    failures = 0
    for i, pdf in enumerate(pdfs, 1):
        failures += _process_one(pdf, args, i, total)
    return failures


def _process_parallel(pdfs: list[Path], args, total: int) -> int:
    failures = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _convert_one_file, pdf, args.ocr, args.engine, args.lang, args.force
            ): (i, pdf)
            for i, pdf in enumerate(pdfs, 1)
        }
        for future in as_completed(futures):
            idx, pdf = futures[future]
            try:
                future.result()
                log.info("[%d/%d] %s -> done", idx, total, pdf.name)
            except Exception:
                log.exception("[%d/%d] %s -> FAILED", idx, total, pdf.name)
                failures += 1
    return failures


def _resolve_lang(pdf: Path, lang_arg: str) -> str:
    if lang_arg == "auto":
        resolved = detect_lang(pdf)
        log.debug("%s -> lang auto-detected: %s", pdf.name, resolved)
        return resolved
    return lang_arg


def _process_one(pdf: Path, args, index: int, total: int) -> int:
    out = resolve_output_path(pdf)
    if should_skip(out, args.force):
        log.info("[%d/%d] %s -> SKIP (exists)", index, total, pdf.name)
        return 0
    try:
        start = time.perf_counter()
        lang = _resolve_lang(pdf, args.lang)
        md, method = convert_pdf(pdf, args.ocr, args.engine, lang)
        elapsed = time.perf_counter() - start
        write_output(out, md)
        log.info("[%d/%d] %s -> %s lang=%s (%.1fs)", index, total, pdf.name, method, lang, elapsed)
        return 0
    except Exception:
        log.exception("[%d/%d] %s -> FAILED", index, total, pdf.name)
        return 1


def _convert_one_file(
    pdf: Path, ocr_mode: str, engine: str, lang: str, force: bool
) -> None:
    """Standalone function for parallel execution."""
    out = resolve_output_path(pdf)
    if should_skip(out, force):
        return
    resolved_lang = _resolve_lang(pdf, lang)
    md, _ = convert_pdf(pdf, ocr_mode, engine, resolved_lang)
    write_output(out, md)


if __name__ == "__main__":
    main()
