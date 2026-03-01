"""Evervault Architect MCP server.

FastMCP server with 7 tools (Phase 1-3):
- ev_encrypt: encrypt data via Evervault API
- ev_inspect: inspect encrypted tokens for metadata
- ev_schema_suggest: analyze schemas for PII/PCI fields
- ev_docs_query: query bundled Evervault documentation
- ev_relay_create: create an Evervault Relay
- ev_relay_list: list all Relays for the current app
- ev_function_run: run an Evervault Function
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP

from evervault_mcp.demo_mode import with_fallback
from evervault_mcp.ev_api import EvervaultClient
from evervault_mcp.redact import setup_logging
from evervault_mcp.schema_analyzer import analyze_schema

log = logging.getLogger("evervault_mcp.server")

DOCS_PATH = Path(__file__).parent / "docs_context.md"

mcp = FastMCP(
    "Evervault Architect",
    instructions=(
        "Architect, deploy, and audit Evervault security infrastructure "
        "directly in your IDE."
    ),
)

# lazily initialized on first tool call
_client: EvervaultClient | None = None


def _get_client() -> EvervaultClient:
    global _client
    if _client is None:
        _client = EvervaultClient()
    return _client


# -- tools --------------------------------------------------------------------


@mcp.tool()
@with_fallback("ev_encrypt")
async def ev_encrypt(
    payload: dict | list | str | int | bool,
    role: str | None = None,
) -> dict[str, Any]:
    """Encrypt data via the Evervault API.

    Accepts any valid JSON value (object, array, string, number, boolean).
    Returns the same structure with values replaced by ev:... ciphertext tokens.

    Args:
        payload: the data to encrypt. Can be any valid JSON value.
        role: optional data role for deterministic encryption (e.g. "email").
    """
    client = _get_client()
    result = await client.encrypt(payload)
    return {"encrypted": result}


@mcp.tool()
@with_fallback("ev_inspect")
async def ev_inspect(tokens: list[str]) -> dict[str, Any]:
    """Inspect encrypted tokens to retrieve metadata without decrypting.

    The Evervault API accepts a single token per request. This tool iterates
    over the provided list and assembles a combined result.

    Args:
        tokens: list of ev:... ciphertext strings to inspect.
    """
    client = _get_client()
    results = await client.inspect_many(tokens)
    return {"inspections": results}


@mcp.tool()
async def ev_schema_suggest(schema: dict[str, Any]) -> dict[str, Any]:
    """Analyze a JSON schema or payload for PII/PCI fields.

    Pattern-matches field names against known sensitive data patterns and
    recommends standard or deterministic encryption. Recommendations are
    advisory only -- actual encryption behavior is controlled by the role
    parameter in ev_encrypt.

    Args:
        schema: a JSON object whose keys represent field names.
    """
    result = analyze_schema(schema)
    result["_source"] = "local"
    return result


@mcp.tool()
async def ev_docs_query(question: str) -> dict[str, Any]:
    """Query bundled Evervault documentation for contextual answers.

    Returns the full documentation context for the LLM to extract a
    concise answer. Covers core concepts, Relay, Functions, Enclaves,
    encryption types, API reference, and compliance.

    Args:
        question: natural-language question about Evervault.
    """
    if not DOCS_PATH.exists():
        return {
            "error": "docs_context.md not found",
            "_source": "local",
        }
    content = DOCS_PATH.read_text(encoding="utf-8")
    return {
        "question": question,
        "documentation": content,
        "_source": "local",
    }


@mcp.tool()
@with_fallback("ev_relay_create")
async def ev_relay_create(
    destination_domain: str,
    routes: list[dict[str, Any]],
    encrypt_empty_strings: bool = False,
) -> dict[str, Any]:
    """Create an Evervault Relay -- a network proxy that encrypts/decrypts data in transit.

    The tool accepts snake_case parameters; the API client maps them to
    camelCase for the Evervault API.

    Args:
        destination_domain: the target API domain (e.g. "api.example.com").
        routes: array of route objects. Each route has method, path, request,
            and response arrays with action/selections. See PRD for structure.
        encrypt_empty_strings: whether to encrypt empty string values.
    """
    client = _get_client()
    result = await client.create_relay(
        destination_domain=destination_domain,
        routes=routes,
        encrypt_empty_strings=encrypt_empty_strings,
    )
    return {"relay": result}


@mcp.tool()
@with_fallback("ev_relay_list")
async def ev_relay_list() -> dict[str, Any]:
    """List all configured Relays for the current Evervault app.

    Returns relays with their IDs, subdomains, destination domains,
    and route configurations.
    """
    client = _get_client()
    relays = await client.list_relays()
    return {"relays": relays, "count": len(relays)}


@mcp.tool()
@with_fallback("ev_function_run")
async def ev_function_run(
    function_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run an Evervault Function -- secure serverless code that auto-decrypts data.

    Encrypted values in the payload are automatically decrypted inside the
    function's secure environment. Your infrastructure never sees plaintext.

    Args:
        function_name: name of the deployed function to run.
        payload: JSON payload to pass to the function (can include ev:... tokens).
    """
    client = _get_client()
    result = await client.run_function(
        function_name=function_name,
        payload=payload,
    )
    return {"function_result": result}


# -- entry point --------------------------------------------------------------


def main() -> None:
    """Start the MCP server."""
    load_dotenv()
    setup_logging()
    log.info("starting Evervault Architect MCP server")
    mcp.run(show_banner=False)
