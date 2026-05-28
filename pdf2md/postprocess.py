"""Post-processing for extracted Markdown text."""
from __future__ import annotations

import re


def clean_markdown(text: str) -> str:
    """Collapse excess blank lines and strip trailing whitespace."""
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    # Collapse runs of >2 blank lines to 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Ensure single trailing newline
    text = text.strip("\n") + "\n"
    return text
