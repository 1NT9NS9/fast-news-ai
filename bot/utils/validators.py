"""
Input validation helpers for user-provided Telegram channel data.

These functions centralize the sanitization logic used by handlers and services
to reduce the likelihood of Server-Side Request Forgery (SSRF) and similar
attacks that rely on crafted channel identifiers.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_CHANNEL_PATTERN = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")
_SCRAPE_BASE_URL = "https://t.me/s/"


def validate_channel_name(name: str) -> str:
    """
    Validate a Telegram channel identifier and return it with a leading '@'.

    Args:
        name: The raw channel identifier supplied by a user or external source.

    Returns:
        The canonical channel identifier (always prefixed with '@').

    Raises:
        ValueError: If the identifier is missing, incorrectly formatted, or
            contains characters that could be used for injection.
    """

    if not isinstance(name, str):
        raise ValueError("Channel name must be a string.")

    candidate = name.strip()
    if not candidate:
        raise ValueError("Название канала не может быть пустым.")
    if "://" in candidate:
        raise ValueError("Название канала не должно содержать схему URL")

    if not _CHANNEL_PATTERN.fullmatch(candidate):
        raise ValueError(
            "Название канала должно содержать от 5 до 32 символов:"
            "букв, цифр или подчеркивания. Должно начинаться с «@»."
        )

    # Remove leading '@' if present so we can canonicalize it.
    normalized = candidate.lstrip("@")
    return f"@{normalized}"


def validate_scrape_url(channel: str) -> str:
    """
    Build and validate the Telegram scrape URL for a given channel.

    Args:
        channel: The channel identifier, with or without the leading '@'.

    Returns:
        A fully-qualified https URL pointing to the Telegram channel's public
        feed in the `/s/` namespace.

    Raises:
        ValueError: If the resulting URL is not an https link to `t.me`.
    """

    canonical_channel = validate_channel_name(channel)
    slug = canonical_channel[1:]

    url = f"{_SCRAPE_BASE_URL}{slug}"

    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Scrape URL must use https.")
    if parsed.netloc.lower() != "t.me":
        raise ValueError("Scrape URL must target t.me.")
    if parsed.path.count("/") != 2 or not parsed.path.startswith("/s/"):
        raise ValueError("Scrape URL must match https://t.me/s/<channel>.")

    return url
