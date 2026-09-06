from __future__ import annotations

import re

# Markdown heading: '#' 到 '######' + 空格 + 内容
_HEADING_RE = re.compile(r"^(#{1,6} .+)$", re.MULTILINE)
# 句尾： 中英文句号/问好/感叹号 后跟空白，（或字符串结尾）
_SENTENCE_END_RE = re.compile(r"(?<=[。！？.!?])\s+")

def split_markdown(
        text: str,
        *,
        max_chars: int = 800,
        overlapped_percent: float = 0) -> list[str]:
    """
    将markdown分割为chunk
    1. 按heading划 section（heading保留在section头部，作为 anchor）
    2. section 超过max_chars -> 按句子边界继续切
    3. 单句超长 -> 硬按 max_chars 切
    :param text:
    :param max_chars:
    :param overlapped_percent:
    :return:
    """
    if not text.strip():
        return []
    if overlapped_percent < 0 or overlapped_percent > 100:
        raise ValueError(
            f"overlapped_percent must be between 0 and 100. got {overlapped_percent}"
        )
    sections = _split_by_heading(text)
    result: list[str] = []
    for section in sections:
        stripped = section.strip()
        if not stripped:
            continue
        if len(stripped) <= max_chars:
            result.append(stripped)
        else:
            result.extend(_split_by_section(stripped, max_chars))
    return _apply_overlap(result, overlapped_percent)

def _split_by_heading(text: str) -> list[str]:
    """
    按照heading 划分。每个section以heading开头，首个section可能无heading
    :param text:
    :return:
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [text]
    sections: list[str] = []
    #第一个 heading之前的正文
    if matches[0].start() > 0:
        #
        sections.append(text[: matches[0].start()])
    for i, m in enumerate(matches):
        #
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[m.start(): end])
    return sections

def _split_by_section(text: str, max_chars: int) -> list[str]:
    """
    把超长句子按照边界 拼装成 <= max_chars 的块
    :param text:
    :param max_chars:
    :return:
    """
    parts = _SENTENCE_END_RE.split(text)

    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(part), max_chars):
                chunks.append(part[i : i + max_chars])
            continue
        candidate = f"{current} {part}".strip() if current else part
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks

def _apply_overlap(chunks: list[str], overlapped_percent: float) -> list[str]:
    if overlapped_percent <= 0 or len(chunks) <= 1:
        return chunks
    out = [chunks[0]]
    for chunk in chunks[1:]:
        prefix = _overlap_prefix(out[-1], overlapped_percent)
        out.append(f"{prefix}{chunk}" if prefix else chunk)
    return out

def _overlap_prefix(prev: str, overlapped_percent: float) -> str:
    """
    取上一块可见字符尾部百分比，
    :param prev:
    :param overlapped_percent:
    :return:
    """
    if not prev:
        return ""
    start = int(len(prev) * (100 - overlapped_percent) / 100.0)
    return prev[start:]