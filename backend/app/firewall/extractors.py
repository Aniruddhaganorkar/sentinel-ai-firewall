from __future__ import annotations

import json
import re
from io import BytesIO

from bs4 import BeautifulSoup

from app.models import SourceType


def extract_untrusted(raw: str, source: SourceType, binary: bytes | None = None) -> str:
    if not raw and not binary:
        return ""
    if source == SourceType.html:
        return _from_html(raw)
    if source == SourceType.markdown:
        return _from_markdown(raw)
    if source == SourceType.json:
        return _from_json(raw)
    if source == SourceType.pdf:
        if binary:
            return _from_pdf_bytes(binary)
        return raw
    if source == SourceType.url:
        return _from_html(raw) if "<" in raw else raw
    return raw


def _from_html(raw: str) -> str:
    from bs4 import Comment

    soup = BeautifulSoup(raw, "lxml")
    hidden = [c.strip() for c in soup.find_all(string=lambda t: isinstance(t, Comment)) if str(c).strip()]
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    if hidden:
        text = text + "\n" + "\n".join(hidden)
    return text


def _from_markdown(raw: str) -> str:
    cleaned = re.sub(r"```.*?```", " ", raw, flags=re.S)
    cleaned = re.sub(r"`[^`]+`", " ", cleaned)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    return cleaned


def _from_json(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    parts: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            parts.append(node)

    walk(data)
    return "\n".join(parts) if parts else raw


def _from_pdf_bytes(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)
