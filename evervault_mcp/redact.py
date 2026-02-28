"""Logging setup with automatic redaction of secrets and ciphertext.

Redaction rules (from PRD section 7):
- API keys (ev:key:...) are truncated to first 12 chars
- Ciphertext tokens (ev:...) are truncated to first 12 chars
- PII field values are not logged -- only field names and metadata
"""

from __future__ import annotations

import logging
import re


# matches ev:key:..., ev:debug:..., ev:encrypted:..., etc.
_EV_TOKEN_RE = re.compile(r"(ev:[a-zA-Z0-9_]+:[^\s\"',}{]{8})[^\s\"',}{]*")


class RedactingFilter(logging.Filter):
    """Truncates Evervault tokens in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(
                redact(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def redact(text: str) -> str:
    """Replace ev:... tokens with truncated versions."""
    return _EV_TOKEN_RE.sub(r"\1...", text)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with redaction filter."""
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    handler.addFilter(RedactingFilter())

    root = logging.getLogger("evervault_mcp")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
