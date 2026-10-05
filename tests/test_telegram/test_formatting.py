"""Tests for Markdown to Telegram HTML conversion."""

from __future__ import annotations

from bot.telegram.formatting import markdown_to_telegram_html


def test_empty_string() -> None:
    assert markdown_to_telegram_html("") == ""


def test_plain_text_is_unchanged() -> None:
    assert markdown_to_telegram_html("Hello everyone") == "Hello everyone"


def test_html_special_characters_are_escaped() -> None:
    assert markdown_to_telegram_html("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_bold() -> None:
    assert markdown_to_telegram_html("This is **bold** text") == "This is <b>bold</b> text"


def test_multiple_bold_spans() -> None:
    assert markdown_to_telegram_html("**a** and **b**") == "<b>a</b> and <b>b</b>"


def test_bold_with_nested_italic() -> None:
    assert markdown_to_telegram_html("**bold *italics* bold**") == "<b>bold <i>italics</i> bold</b>"


def test_italic_with_star() -> None:
    assert markdown_to_telegram_html("This is *italic* text") == "This is <i>italic</i> text"


def test_italic_with_underscore() -> None:
    assert markdown_to_telegram_html("This is _italic_ text") == "This is <i>italic</i> text"


def test_bold_and_italic_triple_marker() -> None:
    assert markdown_to_telegram_html("***both***") == "<b><i>both</i></b>"


def test_underline() -> None:
    assert markdown_to_telegram_html("__underlined__") == "<u>underlined</u>"


def test_strikethrough() -> None:
    assert markdown_to_telegram_html("~~gone~~") == "<s>gone</s>"


def test_spoiler() -> None:
    assert markdown_to_telegram_html("||secret||") == "<tg-spoiler>secret</tg-spoiler>"


def test_snake_case_is_not_italicized() -> None:
    assert markdown_to_telegram_html("snake_case_name") == "snake_case_name"


def test_bullet_list_is_preserved() -> None:
    text = "- one\n- two"
    assert markdown_to_telegram_html(text) == text


def test_unclosed_bold_is_left_as_text() -> None:
    assert markdown_to_telegram_html("**unclosed") == "**unclosed"


def test_inline_code_is_escaped_and_protected() -> None:
    assert (
        markdown_to_telegram_html("Use `print(1 < 2)` now")
        == "Use <code>print(1 &lt; 2)</code> now"
    )


def test_inline_code_keeps_markdown_markers() -> None:
    assert markdown_to_telegram_html("`**not bold**`") == "<code>**not bold**</code>"


def test_bold_containing_inline_code() -> None:
    assert markdown_to_telegram_html("**bold `code`**") == "<b>bold <code>code</code></b>"


def test_fenced_code_block_with_language() -> None:
    assert (
        markdown_to_telegram_html("```python\nprint('hi')\n```")
        == "<pre><code class=\"language-python\">print('hi')</code></pre>"
    )


def test_fenced_code_block_without_language() -> None:
    assert markdown_to_telegram_html("```\ncode\n```") == "<pre>code</pre>"


def test_fenced_code_block_is_escaped() -> None:
    assert (
        markdown_to_telegram_html("```\nif a < b && c > d:\n```")
        == "<pre>if a &lt; b &amp;&amp; c &gt; d:</pre>"
    )


def test_fenced_code_block_keeps_surrounding_text() -> None:
    text = "Before\n```js\nlet x = 1 < 2;\n```\nAfter"
    expected = 'Before\n<pre><code class="language-js">let x = 1 &lt; 2;</code></pre>\nAfter'
    assert markdown_to_telegram_html(text) == expected


def test_fenced_code_block_is_not_styled_inside() -> None:
    assert markdown_to_telegram_html("```\n**bold**\n```") == "<pre>**bold**</pre>"


def test_link() -> None:
    assert (
        markdown_to_telegram_html("[docs](https://example.com?a=1&b=2)")
        == '<a href="https://example.com?a=1&amp;b=2">docs</a>'
    )


def test_link_label_with_formatting() -> None:
    assert (
        markdown_to_telegram_html("[**docs**](https://example.com)")
        == '<a href="https://example.com"><b>docs</b></a>'
    )


def test_link_label_is_escaped() -> None:
    assert (
        markdown_to_telegram_html("[a < b](https://example.com)")
        == '<a href="https://example.com">a &lt; b</a>'
    )


def test_heading_becomes_bold() -> None:
    assert markdown_to_telegram_html("## Header") == "<b>Header</b>"


def test_heading_with_bold_marker_is_normalized() -> None:
    assert markdown_to_telegram_html("### Header **bold**") == "<b>Header bold</b>"


def test_heading_inside_code_block_is_preserved() -> None:
    assert markdown_to_telegram_html("```\n# not a heading\n```") == "<pre># not a heading</pre>"


def test_windows_line_endings_are_normalized() -> None:
    assert markdown_to_telegram_html("a\r\n**b**") == "a\n<b>b</b>"


def test_control_characters_are_stripped() -> None:
    assert markdown_to_telegram_html("a\x00b\x07c") == "abc"
