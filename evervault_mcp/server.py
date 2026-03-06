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
from fastmcp.server.apps import AppConfig
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

from evervault_mcp.demo_mode import DemoMode, get_demo_mode, load_fixture
from evervault_mcp.errors import EvervaultAPIError
from evervault_mcp.ev_api import EvervaultClient
from evervault_mcp.redact import setup_logging
from evervault_mcp.schema_analyzer import analyze_schema
from evervault_mcp.widgets import (
    render_docs_panel,
    render_encrypt_result,
    render_function_run,
    render_inspect_result,
    render_relay_config,
    render_relay_dashboard,
    render_schema_analysis,
)

log = logging.getLogger("evervault_mcp.server")

DOCS_PATH = Path(__file__).parent / "docs_context.md"

_DOCS_SOURCES = [
    {"title": "Core concepts", "url": "https://docs.evervault.com/core-concepts"},
    {"title": "Relay", "url": "https://docs.evervault.com/relay"},
    {"title": "Functions", "url": "https://docs.evervault.com/functions"},
]

mcp = FastMCP(
    "Evervault Architect",
    instructions=(
        "Architect, deploy, and audit Evervault security infrastructure "
        "directly in your IDE."
    ),
)

# lazily initialized on first tool call
_client: EvervaultClient | None = None

# stores latest result for each tool's ui:// resource
_last_results: dict[str, dict[str, Any]] = {}


def _get_client() -> EvervaultClient:
    global _client
    if _client is None:
        _client = EvervaultClient()
    return _client


# -- tools --------------------------------------------------------------------


@mcp.tool(
    app=AppConfig(resource_uri="ui://evervault-architect/encrypt-result.html"),
)
async def ev_encrypt(
    payload: dict | list | str | int | bool,
    role: str | None = None,
) -> ToolResult:
    """Encrypt data via the Evervault API.

    Accepts any valid JSON value (object, array, string, number, boolean).
    Returns the same structure with values replaced by ev:... ciphertext tokens.

    Args:
        payload: the data to encrypt. Can be any valid JSON value.
        role: optional data role for deterministic encryption (e.g. "email").
    """
    mode = get_demo_mode()
    source = "live"

    if mode == DemoMode.MOCK:
        result = load_fixture("ev_encrypt")
        result.pop("_source", None)
        source = "mock"
    else:
        try:
            client = _get_client()
            result = await client.encrypt(payload)
        except (EvervaultAPIError, Exception) as exc:
            if mode == DemoMode.LIVE:
                raise
            log.warning("[ev_encrypt] live call failed (%s), falling back to fixture", str(exc)[:100])
            result = load_fixture("ev_encrypt")
            result.pop("_source", None)
            source = "mock"

    full = {"encrypted": result, "_source": source}
    _last_results["encrypt"] = full

    # count encrypted vs unchanged fields
    enc_count = 0
    unc_count = 0
    if isinstance(result, dict):
        for v in result.values():
            if str(v).startswith("ev:"):
                enc_count += 1
            else:
                unc_count += 1
    total = enc_count + unc_count

    text = (
        f"Encrypted {enc_count} of {total} fields. "
        "The widget above shows each field's status and token. "
        "Do NOT repeat the field table. Instead summarize briefly and focus on:\n"
        "- Which fields were encrypted and why others were left unchanged\n"
        "- Next steps (e.g. store tokens, set up a Relay, inspect tokens)"
    )

    return ToolResult(
        content=[TextContent(type="text", text=text)],
        # send full payload so widgets can render details even when the
        # ui:// resource was prefetched before tool execution
        structured_content=full,
        meta={"ui": {"resourceUri": "ui://evervault-architect/encrypt-result.html"}},
    )


@mcp.tool(
    app=AppConfig(resource_uri="ui://evervault-architect/inspect-result.html"),
)
async def ev_inspect(tokens: list[str]) -> ToolResult:
    """Inspect encrypted tokens to retrieve metadata without decrypting.

    The Evervault API accepts a single token per request. This tool iterates
    over the provided list and assembles a combined result.

    Args:
        tokens: list of ev:... ciphertext strings to inspect.
    """
    mode = get_demo_mode()
    source = "live"

    if mode == DemoMode.MOCK:
        fixture = load_fixture("ev_inspect")
        results = fixture.get("data", fixture.get("inspections", []))
        source = "mock"
    else:
        try:
            client = _get_client()
            results = await client.inspect_many(tokens)
        except (EvervaultAPIError, Exception) as exc:
            if mode == DemoMode.LIVE:
                raise
            log.warning("[ev_inspect] live call failed (%s), falling back to fixture", str(exc)[:100])
            fixture = load_fixture("ev_inspect")
            results = fixture.get("data", fixture.get("inspections", []))
            source = "mock"

    full = {"inspections": results, "_source": source}
    _last_results["inspect"] = full

    # collect stats for model
    categories = list({r.get("category") for r in results if r.get("category")})
    has_roles = any(r.get("role") for r in results)

    text = (
        f"Inspected {len(results)} tokens. "
        "The widget above shows type, category, role, timestamp, and fingerprint "
        "for each token. Do NOT repeat that table. Instead focus on:\n"
        "- Security observations (missing categories, no roles applied)\n"
        "- Whether deterministic encryption roles should be used\n"
        "- Suggested next steps"
    )

    return ToolResult(
        content=[TextContent(type="text", text=text)],
        # send full payload so widgets can render details even when the
        # ui:// resource was prefetched before tool execution
        structured_content=full,
        meta={"ui": {"resourceUri": "ui://evervault-architect/inspect-result.html"}},
    )


@mcp.tool(
    app=AppConfig(resource_uri="ui://evervault-architect/schema-analysis.html"),
)
def ev_schema_suggest(schema: dict[str, Any]) -> ToolResult:
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
    _last_results["schema_analysis"] = result

    summary = result.get("summary", {})
    pci = summary.get("pci_fields", 0)
    pii = summary.get("pii_fields", 0)
    rec = summary.get("recommendation", "")

    log.info(f"ev_schema_suggest called! Found PCI={pci}, PII={pii}. Meta should include AppConfig resource_uri=ui://evervault-architect/schema-analysis.html")

    text = (
        f"Found {pci} PCI and {pii} PII fields out of {summary.get('total_fields', 0)} total. "
        f"{rec}\n\n"
        "The inline widget above shows the full field-by-field table with "
        "sensitivity levels, encryption types, and reasoning. Do NOT repeat "
        "that data. Instead give a brief summary sentence and focus on:\n"
        "- Which fields to encrypt first and why\n"
        "- When deterministic vs standard encryption matters\n"
        "- Suggested next steps (e.g. encrypt sample values, set up a Relay)"
    )

    return ToolResult(
        content=[TextContent(type="text", text=text)],
        # send full payload so widgets can render details even when the
        # ui:// resource was prefetched before tool execution
        structured_content=result,
        meta={"ui": {"resourceUri": "ui://evervault-architect/schema-analysis.html"}},
    )


@mcp.resource("ui://evervault-architect/schema-analysis.html")
def schema_analysis_widget() -> str:
    """Interactive schema analysis widget."""
    data = _last_results.get("schema_analysis", {
        "fields": [],
        "summary": {"total_fields": 0, "pci_fields": 0, "pii_fields": 0, "safe_fields": 0, "recommendation": "No analysis run yet."},
        "_source": "local",
    })
    return render_schema_analysis(data)


@mcp.resource("ui://evervault-architect/encrypt-result.html")
def encrypt_result_widget() -> str:
    """Interactive encryption result widget."""
    data = _last_results.get("encrypt", {
        "encrypted": {},
        "_source": "local",
    })
    return render_encrypt_result(data)


@mcp.resource("ui://evervault-architect/inspect-result.html")
def inspect_result_widget() -> str:
    """Interactive token inspection widget."""
    data = _last_results.get("inspect", {
        "inspections": [],
        "_source": "local",
    })
    return render_inspect_result(data)


@mcp.resource("ui://evervault-architect/docs-panel.html")
def docs_panel_widget() -> str:
    """Interactive documentation panel widget."""
    data = _last_results.get("docs", {
        "question": "",
        "documentation": "",
        "sources": [],
        "_source": "local",
    })
    return render_docs_panel(data)


@mcp.resource("ui://evervault-architect/relay-config.html")
def relay_config_widget() -> str:
    """Interactive relay configuration widget."""
    data = _last_results.get("relay_create", {
        "relay": {},
        "_source": "local",
    })
    return render_relay_config(data)


@mcp.resource("ui://evervault-architect/relay-dashboard.html")
def relay_dashboard_widget() -> str:
    """Interactive relay dashboard widget."""
    data = _last_results.get("relay_list", {
        "relays": [],
        "count": 0,
        "_source": "local",
    })
    return render_relay_dashboard(data)


@mcp.resource("ui://evervault-architect/function-run.html")
def function_run_widget() -> str:
    """Interactive function execution result widget."""
    data = _last_results.get("function_run", {
        "function_name": "---",
        "status": "unknown",
        "execution_time_ms": None,
        "result": {},
        "_source": "local",
    })
    return render_function_run(data)


@mcp.tool(
    app=AppConfig(resource_uri="ui://evervault-architect/docs-panel.html"),
)
async def ev_docs_query(question: str) -> ToolResult:
    """Query bundled Evervault documentation for contextual answers.

    Returns the full documentation context for the LLM to extract a
    concise answer. Covers core concepts, Relay, Functions, Enclaves,
    encryption types, API reference, and compliance.

    Args:
        question: natural-language question about Evervault.
    """
    if not DOCS_PATH.exists():
        return ToolResult(
            content=[TextContent(type="text", text="Error: docs_context.md not found.")],
            structured_content={"error": "docs_context.md not found", "_source": "local"},
            meta={"ui": {"resourceUri": "ui://evervault-architect/docs-panel.html"}},
        )

    content = DOCS_PATH.read_text(encoding="utf-8")
    full = {
        "question": question,
        "documentation": content,
        "sources": _DOCS_SOURCES,
        "_source": "local",
    }
    _last_results["docs"] = full

    text = (
        "Documentation retrieved. The widget above shows the full reference "
        "material. Extract a concise answer to the user's question and cite "
        "relevant sections. Do NOT paste the raw documentation."
    )

    return ToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=full,
        meta={"ui": {"resourceUri": "ui://evervault-architect/docs-panel.html"}},
    )


@mcp.tool(
    app=AppConfig(resource_uri="ui://evervault-architect/relay-config.html"),
)
async def ev_relay_create(
    destination_domain: str,
    routes: list[dict[str, Any]],
    encrypt_empty_strings: bool = False,
) -> ToolResult:
    """Create an Evervault Relay -- a network proxy that encrypts/decrypts data in transit.

    The tool accepts snake_case parameters; the API client maps them to
    camelCase for the Evervault API.

    Args:
        destination_domain: the target API domain (e.g. "api.example.com").
        routes: array of route objects. Each route has method, path, request,
            and response arrays with action/selections. See PRD for structure.
        encrypt_empty_strings: whether to encrypt empty string values.
    """
    mode = get_demo_mode()
    source = "live"

    if mode == DemoMode.MOCK:
        result = load_fixture("ev_relay_create")
        result.pop("_source", None)
        source = "mock"
    else:
        try:
            client = _get_client()
            result = await client.create_relay(
                destination_domain=destination_domain,
                routes=routes,
                encrypt_empty_strings=encrypt_empty_strings,
            )
        except (EvervaultAPIError, Exception) as exc:
            if mode == DemoMode.LIVE:
                raise
            log.warning("[ev_relay_create] live call failed (%s), falling back to fixture", str(exc)[:100])
            result = load_fixture("ev_relay_create")
            result.pop("_source", None)
            source = "mock"

    full = {"relay": result, "_source": source}
    _last_results["relay_create"] = full

    route_count = len(result.get("routes", []))
    text = (
        f"Relay created successfully with {route_count} route(s). "
        "The widget above shows the relay configuration and routes. "
        "Do NOT repeat the route table. Focus on:\n"
        "- How to integrate the relay subdomain into the app\n"
        "- Whether additional routes or response decryption rules are needed\n"
        "- Next steps (e.g. test with sample requests)"
    )

    return ToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=full,
        meta={"ui": {"resourceUri": "ui://evervault-architect/relay-config.html"}},
    )


@mcp.tool(
    app=AppConfig(resource_uri="ui://evervault-architect/relay-dashboard.html"),
)
async def ev_relay_list() -> ToolResult:
    """List all configured Relays for the current Evervault app.

    Returns relays with their IDs, subdomains, destination domains,
    and route configurations.
    """
    mode = get_demo_mode()
    source = "live"

    if mode == DemoMode.MOCK:
        fixture = load_fixture("ev_relay_list")
        # list fixture is wrapped as {"data": [...], "_source": "mock"}
        relays = fixture.get("data", [])
        source = "mock"
    else:
        try:
            client = _get_client()
            relays = await client.list_relays()
        except (EvervaultAPIError, Exception) as exc:
            if mode == DemoMode.LIVE:
                raise
            log.warning("[ev_relay_list] live call failed (%s), falling back to fixture", str(exc)[:100])
            fixture = load_fixture("ev_relay_list")
            relays = fixture.get("data", [])
            source = "mock"

    full = {"relays": relays, "count": len(relays), "_source": source}
    _last_results["relay_list"] = full

    text = (
        f"Found {len(relays)} relay(s). The widget above shows each relay's "
        "domain, routes, and actions. Do NOT repeat the relay table. Focus on:\n"
        "- Coverage gaps (domains or paths not yet proxied)\n"
        "- Whether response decryption rules are needed\n"
        "- Suggested next steps"
    )

    return ToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=full,
        meta={"ui": {"resourceUri": "ui://evervault-architect/relay-dashboard.html"}},
    )


@mcp.tool(
    app=AppConfig(resource_uri="ui://evervault-architect/function-run.html"),
)
async def ev_function_run(
    function_name: str,
    payload: dict[str, Any],
) -> ToolResult:
    """Run an Evervault Function -- secure serverless code that auto-decrypts data.

    Encrypted values in the payload are automatically decrypted inside the
    function's secure environment. Your infrastructure never sees plaintext.

    Args:
        function_name: name of the deployed function to run.
        payload: JSON payload to pass to the function (can include ev:... tokens).
    """
    mode = get_demo_mode()
    source = "live"

    if mode == DemoMode.MOCK:
        result = load_fixture("ev_function_run")
        result.pop("_source", None)
        source = "mock"
    else:
        try:
            client = _get_client()
            result = await client.run_function(
                function_name=function_name,
                payload=payload,
            )
        except (EvervaultAPIError, Exception) as exc:
            if mode == DemoMode.LIVE:
                raise
            log.warning("[ev_function_run] live call failed (%s), falling back to fixture", str(exc)[:100])
            result = load_fixture("ev_function_run")
            result.pop("_source", None)
            source = "mock"

    # flatten: top-level keys instead of nesting inside function_result
    full = {
        "function_name": result.get("function_name", function_name),
        "status": result.get("status", "unknown"),
        "execution_time_ms": result.get("execution_time_ms"),
        "result": result.get("result", {}),
        "_source": source,
    }
    _last_results["function_run"] = full

    name = full["function_name"]
    status = full["status"]
    time_ms = full.get("execution_time_ms", "---")

    text = (
        f"Function '{name}' executed in {time_ms}ms with status '{status}'. "
        "The widget above shows the full result. Do NOT repeat the result "
        "payload. Focus on:\n"
        "- Whether the execution succeeded and what the result means\n"
        "- Performance observations\n"
        "- Suggested next steps"
    )

    return ToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=full,
        meta={"ui": {"resourceUri": "ui://evervault-architect/function-run.html"}},
    )


# -- entry point --------------------------------------------------------------


def main() -> None:
    """Start the MCP server."""
    load_dotenv()
    setup_logging()
    log.info("starting Evervault Architect MCP server")
    mcp.run(show_banner=False)
