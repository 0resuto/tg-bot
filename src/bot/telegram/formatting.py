"""Markdown to Telegram HTML formatting utilities.

LLM responses are authored in Markdown, while the bot sends messages with
``parse_mode="HTML"``. Telegram's HTML mode supports the same formatting set
as MarkdownV2 (bold, italic, underline, strikethrough, spoiler, inline code,
pre blocks and text links) but requires escaping only ``&``, ``<`` and ``>``,
which makes it a safer rendering target for generated text.
"""

from __future__ import annotations

import html
import re

_FENCED_CODE_RE = re.compile(r"```[ \t]*([^\n`]*)\n?(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^()\s]+)\)")
_HEADING_RE = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+(.+?)[ \t]*$")
_PLACEHOLDER_RE = re.compile(r"\x00(\d+)\x00")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_LANGUAGE_RE = re.compile(r"[^0-9A-Za-z_+#.-]")

_BOLD_ITALIC_RE = re.compile(r"\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*")
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_UNDERLINE_RE = re.compile(r"(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)")
_STRIKETHROUGH_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_SPOILER_RE = re.compile(r"\|\|(?=\S)(.+?)(?<=\S)\|\|")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)(?=\S)([^*\n]+?)(?<=\S)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<!\w)_(?!_)(?=\S)([^_\n]+?)(?<=\S)_(?!\w)")


def escape_html(text: str) -> str:
    """Escape characters that are special in Telegram HTML mode."""
    return html.escape(text, quote=False)


def markdown_to_telegram_html(text: str) -> str:
    """Convert a Markdown-formatted string to Telegram-compatible HTML.

    Fenced code blocks and inline code are protected from further parsing so
    their content is only HTML-escaped. Unsupported or malformed constructs are
    left as plain text and safely escaped.
    """
    if not text:
        return text

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS_RE.sub("", text)

    parts: list[str] = []
    position = 0
    for match in _FENCED_CODE_RE.finditer(text):
        parts.append(_convert_inline(text[position : match.start()]))
        parts.append(_render_code_block(match))
        position = match.end()
    parts.append(_convert_inline(text[position:]))
    return "".join(parts)


def _render_code_block(match: re.Match[str]) -> str:
    """Render a fenced code block as a Telegram pre element."""
    language = _LANGUAGE_RE.sub("", match.group(1).strip())
    code = match.group(2)
    if code.endswith("\n"):
        code = code[:-1]
    escaped = escape_html(code)
    if language:
        return f'<pre><code class="language-{language}">{escaped}</code></pre>'
    return f"<pre>{escaped}</pre>"


def _convert_inline(text: str) -> str:
    """Convert inline Markdown constructs within a single text segment."""
    placeholders: list[str] = []

    def store(rendered: str) -> str:
        placeholders.append(rendered)
        return f"\x00{len(placeholders) - 1}\x00"

    text = _INLINE_CODE_RE.sub(lambda m: store(f"<code>{escape_html(m.group(1))}</code>"), text)

    def render_link(match: re.Match[str]) -> str:
        label = _convert_inline(match.group(1))
        url = html.escape(match.group(2), quote=True)
        return store(f'<a href="{url}">{label}</a>')

    text = _LINK_RE.sub(render_link, text)

    # Telegram has no heading entities; render headings as bold lines instead.
    text = _HEADING_RE.sub(
        lambda m: f"**{m.group(1).replace('**', '').strip()}**",
        text,
    )

    text = escape_html(text)

    text = _BOLD_ITALIC_RE.sub(r"<b><i>\1</i></b>", text)
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    text = _UNDERLINE_RE.sub(r"<u>\1</u>", text)
    text = _STRIKETHROUGH_RE.sub(r"<s>\1</s>", text)
    text = _SPOILER_RE.sub(r"<tg-spoiler>\1</tg-spoiler>", text)
    text = _ITALIC_STAR_RE.sub(r"<i>\1</i>", text)
    text = _ITALIC_UNDERSCORE_RE.sub(r"<i>\1</i>", text)

    return _PLACEHOLDER_RE.sub(lambda m: placeholders[int(m.group(1))], text)
