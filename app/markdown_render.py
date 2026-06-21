from __future__ import annotations

import markdown


def render_markdown(text: str) -> str:
    return markdown.markdown(
        text or "",
        extensions=[
            "fenced_code",
            "tables",
            "sane_lists",
            "nl2br",
        ],
        output_format="html5",
    )
