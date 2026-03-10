import re
from typing import Iterable, List


_MD_BOLD_RE = re.compile(r"(\*\*|__)(.*?)\1")
_MD_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_MD_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_MD_LIST_RE = re.compile(r"^\s{0,3}([-*+]|\d+\.)\s+", re.MULTILINE)
_MD_QUOTE_RE = re.compile(r"^\s{0,3}>\s+", re.MULTILINE)
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_HASHTAG_RE = re.compile(r"#\S+")


def strip_markdown(text: str) -> str:
    if not text:
        return ""
    t = text
    t = _MD_BOLD_RE.sub(r"\2", t)
    t = _MD_INLINE_CODE_RE.sub(r"\1", t)
    t = _MD_HEADER_RE.sub("", t)
    t = _MD_LIST_RE.sub("", t)
    t = _MD_QUOTE_RE.sub("", t)
    t = t.replace("**", "").replace("__", "")
    t = t.replace("*", "")
    t = t.replace("`", "")
    t = _MULTI_SPACE_RE.sub(" ", t)
    t = _MULTI_NEWLINE_RE.sub("\n\n", t)
    return t.strip()


def sanitize_title(title: str, max_len: int) -> str:
    t = strip_markdown(title)
    t = t.replace("#", "")
    t = _MULTI_SPACE_RE.sub(" ", t).strip()
    return t[:max_len]


def sanitize_content(content: str, max_len: int, remove_hashtags: bool = True) -> str:
    t = strip_markdown(content)
    if remove_hashtags:
        t = _HASHTAG_RE.sub("", t)
    t = _MULTI_SPACE_RE.sub(" ", t)
    t = _MULTI_NEWLINE_RE.sub("\n\n", t)
    t = t.strip()
    return t[:max_len]


def normalize_tags(tags: Iterable[str], max_tags: int = 8) -> List[str]:
    seen = set()
    cleaned: List[str] = []
    for raw in tags or []:
        t = (raw or "").strip().lstrip("#").replace(" ", "")
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        cleaned.append(t)
        if len(cleaned) >= max_tags:
            break
    return cleaned
