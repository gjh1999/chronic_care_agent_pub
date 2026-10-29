import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BULLET = re.compile(r"^[-*]\s+", re.MULTILINE)


def strip_markdown(text: str) -> str:
    """去掉 LLM 输出中残留的 Markdown 符号(** 加粗、# 标题、列表符),保留换行与编号。"""
    if not text:
        return ""
    return _BULLET.sub("· ", _HEADING.sub("", _BOLD.sub(r"\1", str(text)))).strip()
