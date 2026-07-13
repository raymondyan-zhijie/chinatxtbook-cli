"""Formatting utilities extracted from v1.0.

URL redaction, safe error wrapping, file size formatting.
Source: v1.0 lines 205-220, 623-628.
"""

import re

# Regex for sensitive query parameters in URLs
_QS_SECRET_RE = re.compile(
    r"([?&](?:access_token|private_token|oauth_token|token|auth|api_key|apikey"
    r"|key|password|secret|credential)s?)=[^&\s]+",
    re.IGNORECASE,
)


def redact_url(text: str) -> str:
    """Remove credentials from URLs in text (userinfo@ + sensitive query params).

    Safe to call on any string (e.g. git stderr). Used for logs, state, reports.
    Source: v1.0 lines 209-214.
    """
    if not text:
        return text
    text = re.sub(r"://[^/@\s]+@", "://***@", text)
    return _QS_SECRET_RE.sub(r"\1=***", text)


def safe_error(err, limit: int = 200) -> str:
    """Redact credentials and truncate external error messages for logging.

    All external error output (git stderr, API responses) MUST pass through
    this function before being logged. Source: v1.0 lines 217-220.
    """
    return redact_url(str(err))[:limit]


def fmt_size(n) -> str:
    """Format a byte count as human-readable string.

    Source: v1.0 lines 623-628.
    """
    if n is None:
        return "大小未知"
    if n >= 1024**3:
        return f"{n / 1024 ** 3:.2f} GB"
    return f"{n / 1024 ** 2:.1f} MB"
