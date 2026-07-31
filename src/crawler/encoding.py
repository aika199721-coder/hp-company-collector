"""Deterministic Japanese HTML encoding detection without network access."""

from __future__ import annotations

import codecs
import re
from collections.abc import Mapping

_META_CHARSET = re.compile(rb"<meta[^>]+charset\s*=\s*['\"]?\s*([\w.-]+)", re.IGNORECASE)
_META_HTTP_EQUIV = re.compile(
    rb"<meta[^>]+http-equiv\s*=\s*['\"]?content-type['\"]?[^>]+"
    rb"content\s*=\s*['\"][^'\"]*charset=([\w.-]+)",
    re.IGNORECASE,
)
_MOJIBAKE = ("æ", "ç", "ã", "縺", "繧", "蜿")
_IMPLICIT_LATIN = {"iso-8859-1", "latin-1", "latin1"}


def detect_html_encoding(
    content: bytes,
    headers: Mapping[str, str],
    apparent_encoding: str | None = None,
) -> str:
    """Choose charset, BOM, meta, apparent, UTF-8, then CP932 in strict order."""
    explicit = _header_charset(headers.get("content-type", ""))
    if explicit:
        return explicit
    bom = _bom_encoding(content)
    if bom:
        return bom
    meta = _meta_encoding(content)
    if meta:
        return meta
    candidates: list[str] = []
    apparent = (apparent_encoding or "").strip().lower()
    if apparent and apparent not in _IMPLICIT_LATIN:
        candidates.append(apparent)
    candidates.extend(("utf-8", "cp932", "shift_jis"))
    decoded: list[tuple[int, int, str]] = []
    for order, encoding in enumerate(dict.fromkeys(candidates)):
        try:
            text = content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
        decoded.append((_mojibake_score(text), order, encoding))
        if decoded[-1][0] < 2:
            return encoding
    if decoded:
        return min(decoded)[2]
    return "utf-8"


def _header_charset(content_type: str) -> str | None:
    for parameter in content_type.split(";")[1:]:
        name, separator, value = parameter.strip().partition("=")
        if separator and name.lower() == "charset":
            return value.strip(" \"'").lower() or None
    return None


def _bom_encoding(content: bytes) -> str | None:
    if content.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if content.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    return None


def _meta_encoding(content: bytes) -> str | None:
    head = content[:8192]
    match = _META_CHARSET.search(head) or _META_HTTP_EQUIV.search(head)
    return match.group(1).decode("ascii").lower() if match else None


def _mojibake_score(text: str) -> int:
    return sum(text.count(signal) for signal in _MOJIBAKE)
