from __future__ import annotations
from pathlib import Path

def read_markdown(path: str) -> str:
    """
    Read a markdown file utf-8
    :raises: FileNotFoundError: if file not found
             ValueError: 后缀不是md

    :param path: path to the markdown file
    :return:
    """
    p = Path(path)
    #
    if p.suffix != ".md":
        raise ValueError(f"not a markdown file: {path}")
    if not p.exists():
        raise FileNotFoundError(path)

    return p.read_text(encoding="utf-8")

