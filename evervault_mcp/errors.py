"""Error model for Evervault Architect MCP.

All tools return errors in a consistent envelope so the LLM agent
can recover gracefully and the SE sees actionable messages.
"""

from __future__ import annotations
from typing import Any


class EvervaultAPIError(Exception):
    """Raised when an Evervault API call fails."""

    def __init__(
        self,
        code: str,
        status: int | None = None,
        message: str = "",
        retriable: bool = False,
        suggested_action: str = "",
    ):
        self.code = code
        self.status = status
        self.message = message
        self.retriable = retriable
        self.suggested_action = suggested_action
        super().__init__(message)

    def to_envelope(self) -> dict[str, Any]:
        return make_error_envelope(
            code=self.code,
            status=self.status,
            message=self.message,
            retriable=self.retriable,
            suggested_action=self.suggested_action,
        )


def make_error_envelope(
    code: str,
    status: int | None = None,
    message: str = "",
    retriable: bool = False,
    suggested_action: str = "",
) -> dict[str, Any]:
    """Build a structured error envelope (PRD section 9)."""
    return {
        "error": {
            "code": code,
            "status": status,
            "message": message,
            "retriable": retriable,
            "suggested_action": suggested_action,
        }
    }


def make_fallback_envelope(
    original_error: str,
    fixture_data: dict[str, Any],
) -> dict[str, Any]:
    """Wrap fixture data with fallback metadata for auto-fallback mode."""
    return {
        **fixture_data,
        "_source": "mock",
        "_fallback_reason": original_error,
    }
