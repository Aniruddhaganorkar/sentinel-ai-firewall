from __future__ import annotations

import binascii
import html
import re
import unicodedata
from base64 import b64decode

ZERO_WIDTH = dict.fromkeys(
    map(
        ord,
        [
            "\u200b",
            "\u200c",
            "\u200d",
            "\u2060",
            "\ufeff",
            "\u00ad",
        ],
    )
)

BIDI_MARKS = dict.fromkeys(
    map(
        ord,
        [
            "\u202a",
            "\u202b",
            "\u202c",
            "\u202d",
            "\u202e",
            "\u2066",
            "\u2067",
            "\u2068",
            "\u2069",
        ],
    )
)

BASE64_RE = re.compile(r"\b(?:[A-Za-z0-9+/]{24,}={0,2})\b")
HEX_RE = re.compile(r"\b(?:[0-9a-fA-F]{24,})\b")
URLENC_RE = re.compile(r"(?:%[0-9A-Fa-f]{2}){4,}")


def _strip_controls(text: str) -> str:
    text = text.translate(ZERO_WIDTH).translate(BIDI_MARKS)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cc" or ch in "\n\t")


def _try_b64(blob: str) -> str | None:
    if len(blob) % 4 != 0:
        blob += "=" * (4 - len(blob) % 4)
    try:
        decoded = b64decode(blob, validate=True)
        text = decoded.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if not text or not any(c.isalpha() for c in text):
        return None
    if sum(32 <= ord(c) < 127 or c in "\n\t" for c in text) / len(text) < 0.85:
        return None
    return text


def _try_hex(blob: str) -> str | None:
    if len(blob) % 2:
        return None
    try:
        decoded = bytes.fromhex(blob).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if not any(c.isalpha() for c in decoded):
        return None
    return decoded


def decode_payloads(text: str) -> tuple[str, list[str]]:
    extras: list[str] = []
    decoded = text
    for match in URLENC_RE.findall(text):
        try:
            from urllib.parse import unquote

            extras.append(unquote(match))
        except Exception:
            pass
    for match in BASE64_RE.findall(text):
        got = _try_b64(match)
        if got:
            extras.append(got)
            decoded = decoded.replace(match, f" {got} ")
    for match in HEX_RE.findall(text):
        got = _try_hex(match)
        if got:
            extras.append(got)
            decoded = decoded.replace(match, f" {got} ")
    return decoded, extras


def normalize(text: str) -> dict[str, str]:
    original = text or ""
    unfolded = unicodedata.normalize("NFKC", original)
    unescaped = html.unescape(unfolded)
    stripped = _strip_controls(unescaped)
    decoded, extras = decode_payloads(stripped)
    collapsed = re.sub(r"[ \t]+", " ", decoded)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    matching = collapsed.casefold().strip()
    extra_match = " ".join(extras).casefold()
    return {
        "original": original,
        "decoded": collapsed,
        "matching": (matching + " " + extra_match).strip(),
        "extras": extras,
    }
