"""OCR engine registry."""
from __future__ import annotations

from pdf2md.engines.base import OcrEngine

_ENGINES: dict[str, tuple[str, str]] = {
    "marker": ("pdf2md.engines.marker_engine", "MarkerEngine"),
    "ocrmypdf": ("pdf2md.engines.ocrmypdf_engine", "OcrmypdfEngine"),
    "paddle": ("pdf2md.engines.paddle_engine", "PaddleEngine"),
}


def get_engine(name: str) -> OcrEngine:
    if name not in _ENGINES:
        raise ValueError(f"Unknown engine: {name!r}. Choose from: {', '.join(_ENGINES)}")
    module_path, class_name = _ENGINES[name]
    try:
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()
    except ImportError as exc:
        raise ImportError(
            f"Engine {name!r} requires extra dependencies. "
            f"Install with: pip install pdf2md[{name}]"
        ) from exc
