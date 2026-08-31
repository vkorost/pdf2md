# pdf2md

A Python CLI tool that converts PDFs to Markdown. Automatically routes between fast text extraction and OCR based on whether the PDF has embedded text or is image-only (scanned).

Works on Windows, macOS, and Linux. Tested on Python 3.11+ / Windows 11.

## Why

LLMs work best with Markdown — it's their native format. If you have years of scanned PDFs piling up (medical records, bills, receipts, legal documents, tax forms), getting them into an LLM project means OCR'ing each one and converting to clean text. Doing that manually for hundreds of files is painful.

pdf2md automates the entire pipeline: point it at a folder, and it batch-converts everything to `.md` files ready to drop into a Claude project or any other LLM context. Scanned pages get OCR'd, text pages get extracted directly, and you get clean Markdown out the other end.

This project focuses specifically on PDFs that need OCR — scanned documents, image-only pages, or mixed PDFs. For text-based ebooks (PDF, EPUB, DJVU, FB2) that already have extractable text and don't require OCR, see [ebook2md](https://github.com/vkorost/ebook2md).

## Features

- **Automatic routing**: detects whether each page is text or scanned image; uses fast text extraction where possible, OCR only where needed
- **Batch mode**: convert an entire folder of PDFs in one command, with optional parallel workers
- **Language auto-detection**: detects OCR language from the filename (Cyrillic filenames -> Russian+English, otherwise English); extensible to other languages
- **Three OCR engines**: choose between Marker (best quality), ocrmypdf/Tesseract (lightweight), or PaddleOCR
- **Mixed PDF handling**: PDFs with both text and scanned pages are handled page-by-page: text pages are extracted directly, image pages are OCR'd, results merged in order
- **Column-safe tables**: verifies that table cells were not silently concatenated, and re-extracts preserving column layout if they were (see [Column handling](#column-handling))
- **Text-loss guard**: checks that the Markdown kept the text PyMuPDF can see, and re-extracts if the converter dropped most of it (see [Image-backed PDFs](#image-backed-pdfs))
- **Standalone executable**: can be built into a single `.exe` with PyInstaller (spec file included)

## Install

```bash
# Core (text extraction only, no OCR)
pip install -e .

# With OCR engine of your choice
pip install -e ".[ocrmypdf]"    # ocrmypdf + Tesseract (lightweight, CPU-only)
pip install -e ".[marker]"      # Marker (best quality, GPU optional)
pip install -e ".[paddle]"      # PaddleOCR

# Everything
pip install -e ".[all]"

# Development (includes pytest)
pip install -e ".[dev]"
```

### External dependencies

The `ocrmypdf` engine requires **Tesseract** to be installed separately:

- **Windows**: download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). pdf2md auto-detects `C:\Program Files\Tesseract-OCR\`.
- **Linux**: `sudo apt install tesseract-ocr tesseract-ocr-rus`
- **macOS**: `brew install tesseract tesseract-lang`

## Quick start

```bash
# Convert a single file
pdf2md document.pdf

# Convert all PDFs in the current directory
pdf2md

# Convert all PDFs in a specific directory
pdf2md --dir /path/to/pdfs

# Preview what would happen without writing files
pdf2md --dir /path/to/pdfs --dry-run
```

Output: `Document.pdf` produces `Document.md` in the same directory. UTF-8, LF line endings.

## CLI reference

```
pdf2md [file] [options]
```

| Flag | Default | Description |
|---|---|---|
| `file` | _(none)_ | Single PDF to convert. If omitted, converts all `*.pdf` in the working directory. |
| `--dir PATH` | _(none)_ | Directory containing PDFs to convert. |
| `--force` | off | Overwrite existing `.md` files; otherwise skip with a logged note. |
| `--ocr MODE` | `auto` | `auto` (detect per page), `force` (always OCR), `never` (text extraction only). |
| `--engine NAME` | `ocrmypdf` | OCR engine: `ocrmypdf`, `marker`, or `paddle`. |
| `--lang LANG` | `auto` | OCR language codes. `auto` detects from filename (see below). Or specify explicitly, e.g. `rus+eng`, `deu+eng`. |
| `--layout MODE` | `auto` | Column handling: `auto` (verify and repair), `preserve` (always preserve layout), `off` (no verification). See below. |
| `--workers N` | `1` | Number of parallel workers for batch mode. |
| `--verbose` | off | Log per-page routing decisions and timing. |
| `--dry-run` | off | Print planned actions (convert/skip) without writing files. |

Exit codes: `0` success, `1` partial failure (batch with some failures), `2` fatal error.

## Column handling

Many PDFs — lab reports, invoices, bank statements — position table columns
using absolute coordinates rather than whitespace characters. A converter that
concatenates the text spans of a row without consulting their x-coordinates
glues the cells together:

```
CHLORIDE   |   102   |   98-110 mmol/L      (in the PDF)
CHLORIDE10298-110 mmol/L                    (naive extraction)
```

The result is not just ugly, it is **ambiguous**: you cannot tell whether the
value was 102 or 1029. For numeric documents this is silent data corruption,
which is worse than a hard failure because nothing reports an error.

`--layout auto` (the default) extracts with pymupdf4llm, then checks whether
any row with a real column gap came out glued. If so, it logs a warning and
re-extracts using a geometry-aware path that projects each span onto a
character grid, so column alignment survives:

```
CHLORIDE                 102              98-110 mmol/L
CALCIUM                          10.7 H   8.6-10.3 mg/dL
```

Note that column *position* can itself carry meaning — above, the further-right
value sits in the report's "Out Of Range" column. Flattening to prose destroys
that signal; preserving layout keeps it.

| Mode | Behaviour |
|---|---|
| `auto` | Verify, and repair only when needed. Keeps pymupdf4llm's prose output for ordinary documents. |
| `preserve` | Always use the geometry-aware path. Best for known-tabular corpora. |
| `off` | No verification. Fastest, matches pre-fix behaviour, may glue cells silently. |

### A limitation worth knowing

Some reports encode out-of-range status **only as colour** (a red vs green
result value) with no `H`/`L` text marker. Any text-only extraction — this tool,
`pdftotext`, or OCR — loses that flag. If you need abnormal-value status from
such a report, the colour must be read from the PDF spans directly.

## Image-backed PDFs

Some PDFs render every paragraph as a full-width raster image with a real text
layer sitting on top of it. Merged exam dumps, exported slide decks and some
report generators all do this. `page.get_text()` reads such a page perfectly, so
routing correctly sends it down the fast text path -- and then the Markdown comes
out nearly empty.

The cause is that pymupdf4llm picks its extraction engine at import time:

| `pymupdf.layout` imports | Engine | Behaviour |
|---|---|---|
| yes (needs `onnxruntime`) | ML layout analysis | Reads text that overlaps images |
| no | Legacy heuristic | **Skips every text line whose bbox is inside an image rect** |

On the legacy engine a 22-page document can come back with 3% of its text and no
error: the output is short but not empty, so a plain "did it return anything?"
check passes.

pdf2md guards against this. Under `--layout auto` (the default) it compares the
Markdown's character count against the raw PyMuPDF text and, if less than 60%
survived, re-extracts with image regions ignored, then via the geometry-aware
layout path, then as raw text. `--layout off` skips the check along with the
column verification.

Run with `--verbose` to see which engine is active and how much text survived:

```
DEBUG Text extraction: paper.pdf (pages=None, layout=auto, layout_engine=on)
DEBUG pymupdf4llm coverage 101% (45976 of 45629 chars)
```

```
DEBUG Text extraction: paper.pdf (pages=None, layout=auto, layout_engine=off (onnxruntime missing))
WARNING paper.pdf: pymupdf4llm recovered only 3% of the page text (1387 of 45629 chars); re-extracting.
DEBUG pymupdf4llm(ignore_images) coverage 103% (46900 of 45629 chars)
```

Install `onnxruntime` to get the better engine; the guard is a safety net, not a
substitute for it.

## Batch mode

Convert every PDF in a folder:

```bash
pdf2md --dir /path/to/pdfs
```

- Each `.pdf` produces a `.md` in the same directory
- Existing `.md` files are **skipped** unless `--force` is used
- Progress is logged: `[1/10] filename.pdf -> text lang=eng (1.2s)`
- Use `--workers 4` to process multiple files in parallel

## Language auto-detection

When `--lang` is `auto` (the default), pdf2md inspects the **filename** to choose the OCR language:

| Filename contains | Language code used |
|---|---|
| Cyrillic characters (Russian, Ukrainian, etc.) | `rus+eng` |
| Anything else | `eng` |

You can always override with an explicit `--lang`:

```bash
pdf2md --lang deu+eng german_document.pdf
pdf2md --lang fra+eng french_scan.pdf
```

> **Caveat:** detection is based on the filename, not the document content. A scanned document whose filename does not reflect its language (for example a Russian scan named `report.pdf`) will be misdetected and OCR'd in the wrong language. Pass `--lang` explicitly whenever the filename does not match the content language.

### Extending language detection

The detection logic lives in `pdf2md/lang_detect.py`. To add your own languages, edit the `detect_lang()` function:

```python
# pdf2md/lang_detect.py
import re
from pathlib import Path

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")       # add your own
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")     # add your own

def detect_lang(pdf_path: Path) -> str:
    name = pdf_path.stem
    if _CYRILLIC_RE.search(name):
        return "rus+eng"
    if _CJK_RE.search(name):
        return "chi_sim+eng"
    if _ARABIC_RE.search(name):
        return "ara+eng"
    return "eng"
```

Language codes follow [Tesseract format](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html) when using the `ocrmypdf` engine.

## OCR engines

pdf2md supports three pluggable OCR engines. Install only what you need.

| Engine | Install | Quality | Speed | GPU | Notes |
|---|---|---|---|---|---|
| **ocrmypdf** | `pip install pdf2md[ocrmypdf]` + Tesseract binary | Good | Fast | No | Lightweight. Requires Tesseract on PATH. |
| **Marker** | `pip install pdf2md[marker]` | Best | Slow | Optional | Uses Surya for detection/recognition + layout models. ~2 GB install. Set `TORCH_DEVICE=cpu` for CPU-only. |
| **PaddleOCR** | `pip install pdf2md[paddle]` | Good | Medium | Optional | First run downloads models to `~/.paddleocr`. |

```bash
# Use a specific engine
pdf2md --engine ocrmypdf scanned_doc.pdf
pdf2md --engine marker   scanned_doc.pdf
pdf2md --engine paddle   scanned_doc.pdf
```

If an engine is not installed, you get a clear error message:
```
ImportError: Engine 'marker' requires extra dependencies. Install with: pip install pdf2md[marker]
```

## How routing works

1. Opens the PDF with **PyMuPDF** and counts extractable text characters per page.
2. Classifies each page:
   - Page with >= 50 characters of extractable text -> **text page**
   - Page with < 50 characters -> **image page** (likely scanned)
3. Applies aggregate rules:
   - Total chars across all pages < 100 -> route entire PDF to **OCR**
   - More than 60% image pages -> route to **OCR**
   - Less than 10% image pages -> route to **text** (skip the few image pages)
   - Otherwise -> **mixed** (text-extract text pages, OCR image pages, merge in order)
4. Text pages are extracted using **pymupdf4llm** (preserves headings, lists, tables as Markdown).
5. The result is verified: collapsed column gaps trigger layout-preserving re-extraction, and a character count below 60% of the raw PyMuPDF text triggers the recovery chain (see [Image-backed PDFs](#image-backed-pdfs)).
6. Image pages are rendered at 300 DPI and passed to the selected OCR engine.

> **Content loss warning:** the "less than 10% image pages" rule skips those image pages entirely; their content does not appear in the output. For a mostly-text PDF that contains a few scanned pages you need captured, run it with `--ocr force` to OCR every page.

Use `--verbose` to see per-page classification:

```
[13:18:25] DEBUG Page 1: 338 chars -> text
[13:18:25] DEBUG Page 2: 127 chars -> text
[13:18:25] DEBUG Page 24: 46 chars -> image
[13:18:25] DEBUG Route decision: text (total_chars=1421304)
```

## Python packages used

### Core (always installed)

| Package | Purpose |
|---|---|
| [PyMuPDF](https://pymupdf.readthedocs.io/) (`pymupdf`) | PDF parsing, page text extraction, image rendering at 300 DPI |
| [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm) | Converts PDF pages to Markdown preserving headings, lists, tables |
| [onnxruntime](https://onnxruntime.ai/) | Runs pymupdf4llm's ML layout models. Without it pymupdf4llm falls back to a heuristic that drops text overlapping images (see [Image-backed PDFs](#image-backed-pdfs)). |

### OCR engines (optional, install via extras)

| Package | Extra | Purpose |
|---|---|---|
| [ocrmypdf](https://ocrmypdf.readthedocs.io/) | `[ocrmypdf]` | Tesseract-based OCR with PDF/A output. Uses sidecar text extraction. |
| [marker-pdf](https://github.com/datalab-to/marker) | `[marker]` | ML-based OCR using Surya models. Best quality for complex layouts. |
| [paddleocr](https://github.com/PaddlePaddle/PaddleOCR) | `[paddle]` | Baidu's PP-OCRv5 engine. |
| [paddlepaddle](https://www.paddlepaddle.org.cn/) | `[paddle]` | Deep learning framework required by PaddleOCR. |

### Standard library (no install needed)

`argparse`, `logging`, `pathlib`, `concurrent.futures`, `re`, `tempfile`, `shutil`, `importlib`

## Building a standalone executable

A PyInstaller spec file is included for building a single-file `.exe` (Windows):

```bash
pip install pyinstaller
python -m PyInstaller pdf2md.spec --noconfirm
```

This produces `dist/pdf2md.exe` (~105 MB) with text extraction + ocrmypdf engine bundled. Tesseract still needs to be installed separately on the target machine.

The spec file excludes heavy ML frameworks (torch, scipy, sklearn, etc.) to keep the binary small. If you need the Marker or PaddleOCR engines in the exe, you'll need to adjust the excludes list in `pdf2md.spec`.

`onnxruntime` and `pymupdf/layout/resources/onnx/*.onnx` account for ~35 MB of that and **must not** be excluded: without them the frozen binary silently loses the text of image-backed PDFs (see [Image-backed PDFs](#image-backed-pdfs)). Confirm a build is healthy with:

```bash
dist/pdf2md.exe some.pdf --force --verbose   # expect: layout_engine=on
```

## Project structure

```
pdf2md/
  __init__.py
  __main__.py            # entry point: python -m pdf2md
  cli.py                 # argparse CLI, dispatch, batch processing
  converter.py           # core routing + conversion logic
  router.py              # text-vs-image page classification
  text_extract.py        # pymupdf4llm wrapper, column verification, raw fallback
  layout.py              # column-preserving extraction + collapse detection
  lang_detect.py         # filename-based language auto-detection
  postprocess.py         # whitespace cleanup, blank-line collapse
  io_utils.py            # path handling, overwrite logic, logging
  engines/
    __init__.py          # engine registry with lazy imports
    base.py              # OcrEngine protocol
    marker_engine.py     # Marker engine
    ocrmypdf_engine.py   # ocrmypdf/Tesseract engine
    paddle_engine.py     # PaddleOCR engine
tests/
  conftest.py            # synthetic PDF generators for tests
  test_router.py         # page classification and routing tests
  test_text_extract.py   # text extraction tests
  test_layout.py         # column preservation and collapse-detection tests
  test_engines.py        # OCR engine tests (skipped if not installed)
  test_cli.py            # CLI integration tests
pyproject.toml
pdf2md.spec              # PyInstaller spec for standalone exe
```

## Running tests

```bash
pip install -e ".[dev,ocrmypdf]"
python -m pytest tests/ -v
```

Engine tests are automatically **skipped** if the corresponding engine package is not installed.

## License

AGPL-3.0. This is required by the dependency stack, not a free choice: PyMuPDF and pymupdf4llm are AGPL-3.0, and Marker's code is GPL-3.0. Any distributed work combining them inherits the AGPL terms.

### Dependency licenses

| Package | License |
|---|---|
| PyMuPDF, pymupdf4llm | AGPL-3.0 (commercial license available from Artifex) |
| marker-pdf (code) | GPL-3.0-or-later |
| marker-pdf (model weights) | Modified AI Pubs OpenRAIL-M: free for research, personal use, and organizations under $2M funding/revenue |
| ocrmypdf | MPL-2.0 |
| Tesseract, PaddleOCR, PaddlePaddle | Apache-2.0 |

Organizations above Marker's $2M revenue threshold need a commercial Marker license from Datalab to use the `marker` engine.
