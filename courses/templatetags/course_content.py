from urllib.parse import parse_qs, urlparse

import bleach
import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_MARKDOWN_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
_MARKDOWN_ATTRIBUTES = {"a": ["href", "rel", "target"], "code": ["class"]}


@register.filter
def render_markdown(value):
    """Render learner-facing Markdown while keeping generated and manual HTML safe."""
    rendered = markdown.markdown(value or "", extensions=["extra", "sane_lists", "nl2br"])
    cleaned = bleach.clean(
        rendered,
        tags=_MARKDOWN_TAGS,
        attributes=_MARKDOWN_ATTRIBUTES,
        protocols={"http", "https"},
        strip=True,
    )
    return mark_safe(cleaned)


@register.filter
def video_embed_url(value):
    """Turn supported teacher-entered video URLs into privacy-friendly iframe URLs."""
    raw_url = (value or "").strip()
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host == "youtube.com":
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/"):
            parts = parsed.path.strip("/").split("/")
            video_id = parts[1] if len(parts) > 1 else ""
    if video_id:
        return f"https://www.youtube-nocookie.com/embed/{video_id}"
    if host == "vimeo.com" and parsed.path.strip("/").isdigit():
        return f"https://player.vimeo.com/video/{parsed.path.strip('/')}"
    if host == "player.vimeo.com" and parsed.path.startswith("/video/"):
        return raw_url
    return ""
