#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.services.knowledge.parser

文档解析与切片工具。支持 `txt`、`md`、`pdf`、`docx` 四种常见格式，将其转换为纯文本 *chunk*，
以便后续交给 `KnowledgeRetriever / ChromaDBVectorMemory` 进行向量化存储。

切片策略说明
--------------
1. **读取原始文本**：根据不同文件类型使用相应解析器获取纯文本。
2. **自然段分割**：以“空行”作为段落分隔符，符合常见写作习惯，能够最大程度保留语义连贯性。
3. **滑窗切片**：当段落超过 ``MAX_CHUNK_CHAR``（默认 1500 字符）时，采用窗口大小 ``WINDOW``
  （默认 800 字符）且重叠 ``OVERLAP``（默认 200 字符）的滑动窗口算法继续细分，既满足嵌入模型
  长度限制，也通过重叠区提供上下文衔接。

所有阈值均可通过环境变量 `KR_CHUNK_MAX_CHAR`、`KR_SLIDE_WINDOW`、`KR_SLIDE_OVERLAP` 或
函数参数进行调整。

文件 I/O 为阻塞操作，因此本模块保持同步实现，并在 FastAPI 端通过
`run_in_threadpool()` 在线程池中执行，避免阻塞事件循环。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import markdown  # lightweight, pure-python HTML renderer (std dep)

try:
    import pdfplumber  # noqa: F401
except ImportError:
    pdfplumber = None  # handled lazily

try:
    import docx  # python-docx
except ImportError:
    docx = None  # handled lazily

from loguru import logger
from app.core.config import settings

# --------------------------- Config -----------------------------------------
# MAX_CHUNK_CHAR = int(os.getenv("KR_CHUNK_MAX_CHAR", "1500"))
# WINDOW = int(os.getenv("KR_SLIDE_WINDOW", "800"))
# OVERLAP = int(os.getenv("KR_SLIDE_OVERLAP", "200"))
MAX_CHUNK_CHAR = settings.MAX_CHUNK_CHAR
WINDOW = settings.WINDOW
OVERLAP = settings.OVERLAP

_BLANK_RE = re.compile(r"\n\s*\n", re.MULTILINE)


class UnsupportedDocumentError(RuntimeError):
    """当上传文件的扩展名不被支持时抛出。"""

# ------------------------- Core helpers -------------------------------------

def _split_into_paragraphs(text: str) -> List[str]:
    """通过空行分段，返回去除首尾空白后的段落列表。"""
    paragraphs = [p.strip() for p in _BLANK_RE.split(text) if p.strip()]
    return paragraphs


def _slide_window(paragraph: str) -> List[str]:
    """对超长段落应用滑动窗口切片，返回多个 chunk 字符串。"""
    if len(paragraph) <= MAX_CHUNK_CHAR:
        return [paragraph]

    chunks: List[str] = []
    start = 0
    while start < len(paragraph):
        end = start + WINDOW
        chunk = paragraph[start:end]
        chunks.append(chunk)
        if end >= len(paragraph):
            break
        start += WINDOW - OVERLAP
    return chunks


def _txt_reader(fp: Path) -> str:
    return fp.read_text(encoding="utf-8", errors="ignore")


def _markdown_reader(fp: Path) -> str:
    """将 Markdown 渲染为 HTML 后再通过正则去除标签，获取纯文本。"""
    raw_md = fp.read_text(encoding="utf-8", errors="ignore")
    # Render to HTML then strip tags using regex (good enough for plain text)
    html = markdown.markdown(raw_md)
    text = re.sub(r"<[^>]+>", "", html)
    return text


def _pdf_reader(fp: Path) -> str:
    if pdfplumber is None:
        raise ImportError("解析 PDF 需安装 pdfplumber，请执行 `pip install pdfplumber`。")
    texts: List[str] = []
    with pdfplumber.open(str(fp)) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return "\n\n".join(texts)


def _docx_reader(fp: Path) -> str:
    if docx is None:
        raise ImportError("解析 DOCX 需安装 python-docx，请执行 `pip install python-docx`。")
    d = docx.Document(str(fp))
    texts = [p.text for p in d.paragraphs if p.text]
    return "\n\n".join(texts)


_READERS = {
    ".txt": _txt_reader,
    ".md": _markdown_reader,
    ".markdown": _markdown_reader,
    ".pdf": _pdf_reader,
    ".docx": _docx_reader,
}


def extract_chunks(file_path: Path, base_metadata: Dict[str, str] | None = None) -> List[Dict]:
    """Parse *file_path* and return list of dicts with ``content`` & ``metadata``.

    base_metadata will be merged into each chunk's metadata with extra fields:
    ``source`` (filename), ``chunk_id`` (idx), and for pdf/docx page numbers if available
    (not implemented yet – future work).
    """
    suffix = file_path.suffix.lower()
    if suffix not in _READERS:
        raise UnsupportedDocumentError(f"Unsupported file type: {suffix}")

    logger.debug(f"Parsing document: {file_path.name} (type={suffix})")
    raw_text = _READERS[suffix](file_path)

    chunks: List[Dict] = []
    paragraphs = _split_into_paragraphs(raw_text)
    for para_idx, para in enumerate(paragraphs):
        sub_chunks = _slide_window(para)
        for idx, chunk in enumerate(sub_chunks):
            meta = {
                "source": file_path.name,
                "para_idx": para_idx,
                "sub_idx": idx,
                **(base_metadata or {}),
            }
            chunks.append({"content": chunk, "metadata": meta})
    return chunks


__all__ = ["extract_chunks", "UnsupportedDocumentError"]
