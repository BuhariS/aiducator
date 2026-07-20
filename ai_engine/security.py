import hashlib
import re
from urllib.parse import urlparse

import bleach
from django.conf import settings
from django.core.exceptions import ValidationError

MAX_PROMPT_LENGTH = 4_000
MAX_ANSWER_LENGTH = 12_000
ALLOWED_HTML_TAGS = {
    "br",
    "code",
    "em",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?previous\s+instructions?\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(?:all\s+)?(?:previous|earlier)\s+instructions?\b", re.IGNORECASE),
    re.compile(r"\b(system|developer)\s+message\s*:", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+(?:an?\s+)?(?:unrestricted|jailbreak)", re.IGNORECASE),
)
DANGEROUS_OUTPUT_PATTERNS = (
    re.compile(r"<\s*script\b", re.IGNORECASE),
    re.compile(r"<\s*(?:iframe|object|embed)\b", re.IGNORECASE),
    re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE),
    re.compile(r"\bjavascript\s*:", re.IGNORECASE),
    re.compile(r"\bdata\s*:\s*text/html", re.IGNORECASE),
)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")


def clean_input(value: str, *, field_name: str, max_length: int) -> str:
    if value is None:
        return ""
    value = str(value).replace("\x00", "").strip()
    if len(value) > max_length:
        raise ValidationError(f"{field_name} must be {max_length} characters or fewer.")
    return value


def reject_prompt_injection(value: str, *, field_name: str = "Prompt") -> str:
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(value):
            raise ValidationError(
                f"{field_name} contains an instruction override. Describe the learning goal directly."
            )
    return value


def sanitize_html(value: str) -> str:
    return bleach.clean(
        value or "",
        tags=ALLOWED_HTML_TAGS,
        attributes={},
        protocols={"http", "https"},
        strip=True,
    )


def moderate_text(value: str, *, field_name: str = "AI output") -> str:
    for pattern in DANGEROUS_OUTPUT_PATTERNS:
        if pattern.search(value or ""):
            raise ValidationError(f"{field_name} contains unsafe executable markup or URL content.")
    return value


def moderate_payload(payload, *, field_name: str = "AI output"):
    if isinstance(payload, str):
        return moderate_text(payload, field_name=field_name)
    if isinstance(payload, dict):
        return {key: moderate_payload(value, field_name=field_name) for key, value in payload.items()}
    if isinstance(payload, list):
        return [moderate_payload(value, field_name=field_name) for value in payload]
    return payload


def redact_provider_text(value: str, *, max_length: int) -> str:
    value = clean_input(value, field_name="Provider input", max_length=max_length)
    value = EMAIL_PATTERN.sub("[email removed]", value)
    value = PHONE_PATTERN.sub("[phone removed]", value)
    return value


def allowed_embed_url(value: str, *, field_name: str = "URL") -> str:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed_hosts = {
        item.strip().lower().rstrip(".")
        for item in getattr(settings, "AI_ALLOWED_EMBED_HOSTS", "").split(",")
        if item.strip()
    }
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port:
        raise ValidationError(f"{field_name} must be an HTTPS URL without credentials or a custom port.")
    if not any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
        raise ValidationError(f"{field_name} uses a host that Aiducator does not allow for embeds.")
    return value.strip()


def is_youtube_video_url(value: str) -> bool:
    """Return whether a URL points to a specific YouTube video, not a search page."""
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.").rstrip(".")
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        return False
    if host == "youtu.be":
        return bool(parsed.path.strip("/"))
    if host != "youtube.com":
        return False
    if parsed.path == "/watch":
        return bool(parsed.query and "v=" in parsed.query)
    return parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/")


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
