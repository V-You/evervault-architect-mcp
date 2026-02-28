"""Demo reliability mode for pre-sales demos.

Supports three modes (from PRD section 8):
- live:          all tools call the real Evervault API
- mock:          all tools return canned fixture data, no network
- auto-fallback: try live, fall back to fixtures on failure (default)
"""

from __future__ import annotations

import json
import logging
import os
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Awaitable

from evervault_mcp.errors import EvervaultAPIError, make_fallback_envelope

log = logging.getLogger("evervault_mcp.demo")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DemoMode(Enum):
    LIVE = "live"
    MOCK = "mock"
    AUTO_FALLBACK = "auto-fallback"


def get_demo_mode() -> DemoMode:
    """Read EV_DEMO_MODE from env. Defaults to auto-fallback."""
    raw = os.environ.get("EV_DEMO_MODE", "auto-fallback").lower().strip()
    try:
        return DemoMode(raw)
    except ValueError:
        log.warning("unknown EV_DEMO_MODE '%s', defaulting to auto-fallback", raw)
        return DemoMode.AUTO_FALLBACK


def load_fixture(tool_name: str) -> dict[str, Any]:
    """Load a canned fixture for the given tool."""
    fixture_path = FIXTURES_DIR / f"{tool_name}.json"
    if not fixture_path.exists():
        log.warning("no fixture found for '%s' at %s", tool_name, fixture_path)
        return {"error": {"code": "no_fixture", "message": f"No fixture for {tool_name}"}}
    with open(fixture_path) as f:
        data = json.load(f)
    # normalize: always return a dict so we can attach _source
    if isinstance(data, list):
        return {"data": data, "_source": "mock"}
    data["_source"] = "mock"
    return data


def with_fallback(tool_name: str):
    """Decorator: wraps an async tool function with demo mode support.

    - LIVE: calls the function directly, errors propagate
    - MOCK: skips the function, returns fixture
    - AUTO_FALLBACK: tries the function, returns fixture on failure
    """
    def decorator(fn: Callable[..., Awaitable[dict[str, Any]]]):
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            mode = get_demo_mode()

            if mode == DemoMode.MOCK:
                log.info("[%s] mock mode -- returning fixture", tool_name)
                return load_fixture(tool_name)

            try:
                result = await fn(*args, **kwargs)
                result["_source"] = "live"
                return result
            except (EvervaultAPIError, Exception) as exc:
                if mode == DemoMode.LIVE:
                    # in live mode, surface the error
                    if isinstance(exc, EvervaultAPIError):
                        return exc.to_envelope()
                    raise

                # auto-fallback: return fixture with fallback metadata
                log.warning(
                    "[%s] live call failed (%s), falling back to fixture",
                    tool_name,
                    str(exc)[:100],
                )
                fixture = load_fixture(tool_name)
                return make_fallback_envelope(str(exc)[:200], fixture)

        return wrapper
    return decorator
