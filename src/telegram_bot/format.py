"""Answers in Telegram's format (ADR-0027).

The agent writes Markdown, like the web chat shows. Telegram accepts only a
small set of HTML tags, so the common Markdown is converted, everything else is
escaped, and long answers are split under Telegram's 4096-character limit.
"""

from __future__ import annotations

import html
import re

# Below Telegram's 4096 limit, leaving room for the tags added by to_html.
CHUNK = 3500

_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+")


def split(text: str, limit: int = CHUNK) -> list[str]:
    """Split text into pieces of at most `limit` characters, at paragraph or line ends."""
    pieces: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
        current = ""
        for line in paragraph.split("\n"):
            while len(line) > limit:
                pieces.append(line[:limit])
                line = line[limit:]
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) <= limit:
                current = candidate
            else:
                pieces.append(current)
                current = line
    if current:
        pieces.append(current)
    return pieces or [""]


def _inline(line: str) -> str:
    """Convert inline Markdown in one escaped line; code spans are left as they are."""
    codes: list[str] = []

    def keep_code(match: re.Match[str]) -> str:
        codes.append(f"<code>{match.group(1)}</code>")
        return f"\x00{len(codes) - 1}\x00"

    line = _CODE.sub(keep_code, line)
    line = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', line)
    line = _BOLD.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", line)
    line = _ITALIC.sub(r"<i>\1</i>", line)
    return re.sub("\x00(\\d+)\x00", lambda m: codes[int(m.group(1))], line)


def to_html(markdown: str) -> str:
    """Return the Markdown as Telegram HTML. Tables and code blocks stay monospaced."""
    out: list[str] = []
    block: list[str] = []
    in_fence = False

    def flush_block() -> None:
        if block:
            out.append("<pre>" + html.escape("\n".join(block), quote=False) + "</pre>")
            block.clear()

    for raw in markdown.split("\n"):
        if raw.strip().startswith("```"):
            if in_fence:
                flush_block()
            in_fence = not in_fence
            continue
        if in_fence or raw.lstrip().startswith("|"):
            block.append(raw)
            continue
        flush_block()
        line = html.escape(raw)
        if heading := _HEADING.match(line):
            out.append(f"<b>{_inline(heading.group(1))}</b>")
            continue
        line = _BULLET.sub(lambda m: f"{m.group(1)}• ", line)
        out.append(_inline(line))
    flush_block()
    return "\n".join(out)
