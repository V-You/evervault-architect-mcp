# Evervault Architect MCP

**Architect, deploy, and audit Evervault security infrastructure in your IDE**

This MCP server gives your AI agent access to [Evervault](https://docs.evervault.com/). Encrypt data, create Relay proxies, run secure Functions, and analyze schemas for PII.

## Scenario 1: 

| `/evervault` Analyze this schema: | ... | ... | ... |
| :---: | :----: | :----: | :---: |
| <kbd><img src="img/Screenshot_2026-03-01_095737.png" width="99px" /></kbd> | <kbd><img src="img/Screenshot_2026-02-22_201741.png" width="99px" /></kbd> | <kbd><img src="img/Screenshot_2026-02-28_205801.png" width="99px" /></kbd> | <kbd><img src="img/Screenshot_2026-02-22_203609.png" width="99px" /></kbd> |

## Scenario 2: 

| `/evervault` Set up a Relay <br>to intercept card data: | ... | ... | ... |
| :---: | :----: | :----: | :---: |
| <kbd><img src="img/Screenshot_2026-02-22_195923.png" width="99px" /></kbd> | <kbd><img src="img/Screenshot_2026-02-22_201741.png" width="99px" /></kbd> | <kbd><img src="img/Screenshot_2026-02-28_205801.png" width="99px" /></kbd> | <kbd><img src="img/Screenshot_2026-02-22_203609.png" width="99px" /></kbd> |



## Overview

In your IDE, use slash command `/evervault`:

**``/evervault`` Analyze our user-service schema and tell me what's exposed**<br>
**Agent:** Scans the schema, highlights PII fields, recommends encryption types. Renders a color-coded sensitivity tree in the chat.

**``/evervault`` Encrypt this sample user payload** <br>
**Agent:** Calls the Evervault Encrypt API. Shows a before/after diff – plaintext → ev:encrypted: ...

**``/evervault`` Set up a Relay to intercept card data before it hits our DB**<br>
**Agent:** Creates a Relay via the API. Shows a route map widget: source → Relay → destination.

<span style="color: darkgreen;">**Result:** In 5 minutes, you've improved compliance – without leaving the IDE.</span>

---

## Install

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+ (for building widgets)
- VS Code with GitHub Copilot or compatible MCP host
- Evervault account with API credentials

### Install from GitHub (recommended)

```bash
uvx --from git+https://github.com/V-You/evervault-architect-mcp evervault-mcp
```

### Install for local development

```bash
git clone https://github.com/V-You/evervault-architect-mcp.git
cd evervault-architect-mcp
uv sync
uv run python -m evervault_mcp
```

### Environment variables

Create a `.env` file in the project root:

```env
EV_APP_ID=app_77b94737782c
EV_API_KEY=your_api_key_here
EV_DEMO_MODE=auto-fallback    # live | mock | auto-fallback (default)
```

> **Note:** The `.env` file is loaded by the Python server at startup via `python-dotenv`. The `${env:...}` syntax in `mcp.json` reads from the *shell* environment, not `.env`. For local testing, either `export` the vars in your shell or set literal values in `mcp.json`.

### VS Code MCP configuration

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "evervault-architect": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/V-You/evervault-architect-mcp", "evervault-mcp"],
      "env": {
        "EV_APP_ID": "${env:EV_APP_ID}",
        "EV_API_KEY": "${env:EV_API_KEY}"
      }
    }
  }
}
```

---

## Usage

### IDE Skills

| Skill | Persona | When to use |
|---|---|---|
| `/evervault` | Product Developer | *"Set up encryption for my checkout flow"* |
| `/evervault-security` | Security Architect | *"Audit our encryption posture"* |

### Example interactions

**Schema analysis:**
```
> Analyze this JSON schema for PII:
> { "name": "string", "email": "string", "card_number": "string", "address": "string" }
```

**Live encryption:**
```
> Encrypt this payload: { "email": "jane@example.com", "ssn": "123-45-6789" }
```

**Relay creation:**
```
> Create a Relay for api.example.com that encrypts card_number and cvv on POST /checkout
```

**Documentation query:**
```
> What's the difference between Relay and Functions?
```

---

## Architecture

```
IDE (VS Code)
  ├── /evervault             (Skill – developer persona)
  ├── /evervault-security    (Skill – security persona)
  └── LLM routes intent
        ↓
  evervault_mcp/server.py    (FastMCP, stdio transport)
    ├── ev_encrypt            →  POST /encrypt             →  ui://encrypt-result.html
    ├── ev_inspect            →  POST /inspect             →  ui://inspect-result.html
    ├── ev_relay_create       →  POST /relays                        →  ui://relay-config.html
    ├── ev_relay_list         →  GET  /relays                        →  ui://relay-dashboard.html
    ├── ev_function_run       →  POST /functions/{function_name}/runs →  ui://function-run.html
    ├── ev_schema_suggest     →  local pattern matching               →  ui://schema-analysis.html
    └── ev_docs_query         →  bundled docs_context.md              →  ui://docs-panel.html
```

**Transport:** stdio (local). Server runs as a child process of the IDE.

**MCP Apps:** Each tool declares a `ui://` resource via FastMCP's `AppConfig`. The host (VS Code) fetches the HTML via `resources/read` and renders it inside the Chat window -- interactive widgets served directly over the MCP protocol.

### MCP Apps implementation

Three pieces must be wired together for a widget to render inline:

**1. `ui://` resource** -- serves the self-contained HTML.

```python
@mcp.resource("ui://schema-analysis")
def schema_analysis_widget() -> str:
    """Interactive schema analysis widget."""
    return render_schema_analysis(_last_results.get("schema_analysis", {}))
```

The `ui://` URI scheme auto-sets the MIME type to `text/html;profile=mcp-app`.

**2. `AppConfig` on the tool** -- tells the host which resource to render.

```python
@mcp.tool(
    app=AppConfig(resource_uri="ui://schema-analysis"),
)
```

FastMCP merges this into `_meta.ui.resourceUri` on the wire, which the host reads during `tools/list`.

**3. `ToolResult` return value** -- separates LLM-facing text from widget data.

```python
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

return ToolResult(
    content=[TextContent(type="text", text="Concise directive for the LLM")],
    structured_content=result_dict,
    meta={"ui": {"resourceUri": "ui://evervault/<widget-name>.html"}},
)
```

The `meta` dict becomes `_meta` on the wire. VS Code needs `_meta.ui.resourceUri` in the **tool call response** to trigger widget rendering -- this is separate from (and in addition to) `AppConfig`, which only populates `_meta` in `tools/list`. Passing `meta={}` causes an empty `_meta: {}` on the wire, and the host silently skips rendering. The `structured_content` dict is what the widget's HTML/JS reads to populate itself. The `content` text is what the LLM sees and uses to frame its response.

**Adding a new widget:**

1. Write a `render_*()` function in `widgets.py` that returns a self-contained HTML string (use VS Code CSS variables like `--vscode-foreground` for theme integration)
2. The HTML **must** include a `<script>` that performs the MCP Apps `initialize` handshake via `postMessage` -- without it, the host won't display the iframe. The handshake methods use the `ui/` prefix and kebab-case notification names:
   - Send request: `"ui/initialize"` with `protocolVersion: "2025-06-18"`
   - Send notification: `"ui/notifications/initialized"`
   - Listen for: `"ui/notifications/tool-result"` (receives `structuredContent`), `"ui/notifications/host-context-changed"` (theme vars)
   - **Do not** use unprefixed `"initialize"` or camelCase `"hostContextChanged"` -- these will silently fail. See `widgets.py` for the minimal template
3. Use the URI convention `ui://evervault/<widget-name>.html`
4. Register a `@mcp.resource("ui://evervault/<widget-name>.html")` that calls the renderer
5. Add `app=AppConfig(resource_uri="ui://evervault/<widget-name>.html")` to the `@mcp.tool()` decorator
6. Return `ToolResult(content=..., structured_content=..., meta={"ui": {"resourceUri": "ui://evervault/<widget-name>.html"}})` from the tool
7. Optionally store the result in `_last_results` so the resource can serve it on subsequent reads

**Gotchas discovered during the first widget (2026-02-28):**

- `meta={}` produces `_meta: {}` on the wire -- VS Code ignores it. You must explicitly pass the `ui.resourceUri` in `meta` for each tool call response, not just in `AppConfig`.
- Handshake method names are `ui/`-prefixed and kebab-case (`ui/initialize`, `ui/notifications/host-context-changed`). Unprefixed or camelCase variants fail silently.
- Protocol version must be `"2025-06-18"` (the MCP Apps spec date, not the blog date).
- The `@mcp.resource` handler is called on `resources/read` -- it must return valid HTML even before the tool has run (use a sensible empty-state default).

---

## Tools

### `ev_encrypt`

Encrypts data via the [Evervault Encrypt API](https://docs.evervault.com/api#encrypt). Accepts any valid JSON value (object, array, string, number, boolean). Returns the same structure with values replaced by `ev:...` ciphertext.

- **API:** `POST https://api.evervault.com/encrypt`
- **Widget:** Side-by-side diff – plaintext input → encrypted output

### `ev_inspect`

Retrieves metadata for encrypted values (encryption time, data type, role, fingerprint) without decrypting. Accepts an array of `ev:...` tokens and iterates over the single-token `/inspect` API.

- **API:** `POST https://api.evervault.com/inspect` (per token)
- **Widget:** Table of inspected tokens with metadata badges

### `ev_relay_create`

Creates an [Evervault Relay](https://docs.evervault.com/relay) – a network proxy that encrypts/decrypts data in transit.

- **API:** `POST https://api.evervault.com/relays`
- **Widget:** Visual route map – source → Relay → destination

### `ev_relay_list`

Lists all configured Relays for the current app.

- **API:** `GET https://api.evervault.com/relays`
- **Widget:** Dashboard table with Relay names, destinations, and route counts

### `ev_function_run`

Runs an [Evervault Function](https://docs.evervault.com/functions) – secure serverless code that auto-decrypts data at runtime.

- **API:** `POST https://api.evervault.com/functions/{function_name}/runs`
- **Widget:** Execution flow diagram with timing

### `ev_schema_suggest`

Analyzes a JSON payload or schema for PII/PCI fields. Recommends encryption types (Standard vs. Deterministic) based on field usage patterns.

- **Implementation:** Local pattern matching – no API call. Recommendations for deterministic vs. standard encryption are advisory.
- **Widget:** Color-coded schema tree (🔴 PCI, 🟡 PII, 🟢 Safe)

### `ev_docs_query`

Queries bundled Evervault documentation for contextual answers without leaving the IDE.

- **Implementation:** Local – reads bundled `docs_context.md`
- **Widget:** Formatted doc panel with links to official docs

---

## Demo Narratives

### 1. "The Zero-Day Implementation"

> *Your prospect's InfoSec team flagged plaintext emails. You have 15 minutes.*

`ev_schema_suggest` → `ev_encrypt` → `ev_relay_create` → `ev_inspect`

**Closer:** *"5 minutes. Materially improved compliance posture. You sold Time to Market."*

### 2. "The Invisible Migration"

> *Years of unencrypted PII. No code freeze budget.*

`ev_relay_list` → `ev_schema_suggest` → `ev_relay_create` → `ev_encrypt`

**Closer:** *"Modernized security without a single PR to business logic."*

### 3. "The Safe-to-Ship"

> *Developers afraid to touch checkout because of compliance blast radius.*

`ev_function_run` → `ev_relay_create` → `ev_inspect`

**Closer:** *"Evervault isn't a gatekeeper – it's an accelerator."*

### 4. "The Privacy-Preserving AI"

> *CEO wants AI. Legal says no – can't send PII to external LLMs.*

`ev_schema_suggest` → `ev_encrypt` → `ev_relay_create` → `ev_function_run`

**Closer:** *"Privacy is no longer the reason you can't ship AI."*

### 5. "The Invisible Security Team"

> *5 developers, zero security hires, enterprise prospects.*

`ev_schema_suggest` → `ev_relay_create` → `ev_relay_list` → `ev_inspect`

**Closer:** *"The Senior Security Engineer you haven't hired yet."*

---

## Project Structure

```
├── evervault_mcp/                      # Python package
│   ├── __init__.py
│   ├── __main__.py                     # Entry point
│   ├── server.py                       # MCP server (7 tools + 7 ui:// resources)
│   ├── ev_api.py                       # Evervault API client
│   ├── schema_analyzer.py              # PII/PCI pattern matching
│   └── docs_context.md                 # Bundled documentation
├── src/                                # Widget source (React + TypeScript)
│   ├── encrypt-result/
│   ├── inspect-result/
│   ├── relay-config/
│   ├── relay-dashboard/
│   ├── function-run/
│   ├── schema-analysis/
│   └── docs-panel/
├── assets/                             # Built widgets (self-contained HTML)
├── pyproject.toml
├── package.json
├── vite.config.mts
└── .vscode/mcp.json
```



---

## Future Improvements (Deferred from QA-01)

The following items were identified during QA review but deferred from v1 as over-engineering for a demo tool at this stage. Each would meaningfully harden the server for production-grade repeatability.

### 1. Operational NFRs (Correlation IDs, Backoff Matrices, Rate Limit UX)

**Why:** Full observability and graceful degradation under sustained use – correlation IDs let you trace a single demo interaction across tool calls, API requests, and widget renders; backoff policies prevent rate-limit lockouts during rapid-fire demos.

**Deferred because:** v1 already has a 5-second timeout budget and `auto-fallback` mode, which cover the realistic failure modes for a live demo. The additional observability infrastructure (structured logging, trace propagation) adds complexity without improving the demo experience for a single-SE use case.

**How:** Add a `request_id` (UUID) generated per tool invocation, threaded through `ev_api.py` as a header and into widget payloads. Implement exponential backoff with jitter in the API client for `429` responses. Surface rate-limit state in the widget badge (e.g., `🟠 Throttled`). This would change v1's binary live/fallback behavior into a more graceful spectrum: live → throttled → fallback.

### 2. Contract Tests Against API Mock

**Why:** Catches API drift – if Evervault changes their response schema (e.g., adds a required field to `/relays`), contract tests fail before the demo does.

**Deferred because** v1's fixture files already encode the expected response shapes, and `auto-fallback` mode masks API drift during demos. Contract tests add CI/CD overhead that isn't justified until the tool is maintained by more than one person.

**How:** Use the [Evervault OpenAPI spec](https://docs.evervault.com/api-spec.json) to generate a mock server (e.g., Prism). Write pytest contract tests that hit the mock, asserting that `ev_api.py`'s request/response serialization round-trips correctly. Run in CI on every push. This would shift v1's "discover drift at demo time" to "discover drift at CI time."

### 3. Golden Tests for Widget Rendering

**Why:** Visual regression safety – ensures widget HTML renders correctly after React/Vite upgrades or data model changes.

**Deferred because** Widgets are self-contained HTML bundles built infrequently. Until the widget count grows or multiple contributors touch them, manual visual checks during development are sufficient.

**How:** Snapshot each widget's rendered HTML against golden files using Playwright. Diff against baseline on PR. This would change v1's "build and eyeball" workflow to "build, auto-compare, flag regressions."

### 4. Skill Behavior Spec (Prompt Constraints & Guardrails)

**Why:** Prevents the AI agent from making over-strong compliance claims (e.g., "you are now PCI compliant") or invoking tools in unexpected sequences during a demo.

**Deferred because** The skill `.md` files (`SKILL.md`) will naturally define persona boundaries and tool invocation guidance at implementation time. Specifying prompt constraints in the PRD before the tools exist would be speculative – the right guardrails emerge from actual demo rehearsals.

**How:** Add explicit `do_not_claim` lists to each skill's system prompt (e.g., "Never state that this constitutes legal compliance certification"). Add tool-sequence hints (e.g., "Prefer `ev_schema_suggest` before `ev_encrypt` for first-time schemas"). Test with adversarial prompts ("Am I PCI compliant now?") and validate the agent's response stays within bounds. This would change v1's open-ended agent behavior into a guardrailed conversation flow.

---
