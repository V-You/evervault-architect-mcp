"""HTML widget renderers for MCP Apps.

Each function takes tool result data and returns a self-contained HTML string
for rendering in the VS Code chat panel via the ui:// resource protocol.
"""

from __future__ import annotations

from typing import Any


def render_schema_analysis(data: dict[str, Any]) -> str:
    """Render ev_schema_suggest results as an interactive HTML widget."""
    fields = data.get("fields", [])
    summary = data.get("summary", {})
    source = data.get("_source", "unknown")

    field_rows = ""
    for f in fields:
        sensitivity = f.get("sensitivity", "safe")
        icon = {"pci": "&#x1F534;", "pii": "&#x1F7E1;", "safe": "&#x1F7E2;"}.get(
            sensitivity, ""
        )
        enc = f.get("suggested_encryption", "none")
        enc_badge = ""
        if enc == "deterministic":
            enc_badge = '<span class="badge det">deterministic</span>'
        elif enc == "standard":
            enc_badge = '<span class="badge std">standard</span>'
        else:
            enc_badge = '<span class="badge safe">none</span>'

        sensitivity_class = sensitivity
        field_rows += f"""
        <tr class="{sensitivity_class}">
            <td class="field-path"><code>{f.get("field_path", "")}</code></td>
            <td class="sensitivity">{icon} {sensitivity.upper()}</td>
            <td>{enc_badge}</td>
            <td class="reasoning">{f.get("reasoning", "")}</td>
        </tr>"""

    total = summary.get("total_fields", 0)
    pci = summary.get("pci_fields", 0)
    pii = summary.get("pii_fields", 0)
    safe = summary.get("safe_fields", 0)
    rec = summary.get("recommendation", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
    color: var(--vscode-foreground, #d4d4d4);
    background: var(--vscode-editor-background, #1e1e1e);
    padding: 12px;
  }}
  .header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }}
  .title {{
    font-size: 14px;
    font-weight: 600;
  }}
  .source-badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: {("#2d5a2d" if source == "live" else "#5a4a1a" if source == "mock" else "#2a3a5a")};
    color: {("#4ec94e" if source == "live" else "#e6c84e" if source == "mock" else "#7aa3e6")};
  }}
  .stats {{
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
  }}
  .stat {{
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
    text-align: center;
    flex: 1;
  }}
  .stat-value {{
    font-size: 20px;
    font-weight: 700;
  }}
  .stat-label {{
    font-size: 11px;
    opacity: 0.7;
    margin-top: 2px;
  }}
  .stat.pci .stat-value {{ color: #f44; }}
  .stat.pii .stat-value {{ color: #fa0; }}
  .stat.safe .stat-value {{ color: #4c4; }}
  .recommendation {{
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 12px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
    border-left: 3px solid {("#f44" if pci > 0 else "#fa0" if pii > 0 else "#4c4")};
    font-size: 12px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  th {{
    text-align: left;
    padding: 6px 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    opacity: 0.6;
    border-bottom: 1px solid var(--vscode-widget-border, #333);
  }}
  td {{
    padding: 6px 8px;
    border-bottom: 1px solid var(--vscode-widget-border, #222);
    vertical-align: top;
  }}
  tr.pci {{ background: rgba(255, 68, 68, 0.06); }}
  tr.pii {{ background: rgba(255, 170, 0, 0.06); }}
  .field-path code {{
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
  }}
  .sensitivity {{ white-space: nowrap; }}
  .reasoning {{
    font-size: 11px;
    opacity: 0.7;
    max-width: 260px;
  }}
  .badge {{
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 500;
  }}
  .badge.det {{ background: #3a2a1a; color: #fa0; }}
  .badge.std {{ background: #2a1a1a; color: #f66; }}
  .badge.safe {{ background: #1a2a1a; color: #6c6; }}
</style>
</head>
<body>
  <div class="header">
    <span class="title">Schema analysis</span>
    <span class="source-badge" id="source-badge">{source}</span>
  </div>
  <div class="stats">
    <div class="stat pci">
      <div class="stat-value" id="stat-pci">{pci}</div>
      <div class="stat-label">PCI fields</div>
    </div>
    <div class="stat pii">
      <div class="stat-value" id="stat-pii">{pii}</div>
      <div class="stat-label">PII fields</div>
    </div>
    <div class="stat safe">
      <div class="stat-value" id="stat-safe">{safe}</div>
      <div class="stat-label">Safe fields</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-total">{total}</div>
      <div class="stat-label">Total</div>
    </div>
  </div>
  <div class="recommendation" id="recommendation">{rec}</div>
  <table>
    <thead>
      <tr><th>Field</th><th>Sensitivity</th><th>Encryption</th><th>Reason</th></tr>
    </thead>
    <tbody id="field-rows">{field_rows}
    </tbody>
  </table>
  <script>
    // MCP Apps handshake -- robust async pattern matching Swarmia
    const pendingReqs = new Map();
    let msgId = 1;

    function mcpRequest(method, params) {{
      return new Promise((resolve, reject) => {{
        const id = msgId++;
        pendingReqs.set(id, {{ resolve, reject }});
        window.parent.postMessage({{ jsonrpc: "2.0", id, method, params: params || {{}} }}, "*");
      }});
    }}

    function mcpNotify(method, params) {{
      window.parent.postMessage({{ jsonrpc: "2.0", method, params: params || {{}} }}, "*");
    }}

    function applyHostContext(ctx) {{
      if (ctx && ctx.styles && ctx.styles.variables) {{
        for (const [k, v] of Object.entries(ctx.styles.variables)) {{
          document.documentElement.style.setProperty(k, v);
        }}
      }}
      if (ctx && ctx.theme) {{
        document.documentElement.style.colorScheme = ctx.theme;
      }}
    }}

    window.addEventListener("message", (e) => {{
      const data = e.data;
      if (!data || data.jsonrpc !== "2.0") return;

      if (data.id !== undefined && (data.result !== undefined || data.error)) {{
        const p = pendingReqs.get(data.id);
        if (p) {{
          pendingReqs.delete(data.id);
          if (data.error) p.reject(new Error(data.error.message));
          else p.resolve(data.result);
        }}
        return;
      }}
      
      if (data.method === "ui/notifications/host-context-changed") {{
        applyHostContext(data.params);
      }}

      if (data.method === "ui/notifications/tool-result" && data.params) {{
        const sc = data.params.structuredContent;
        if (sc) {{
          applyToolResult(sc);
        }}
      }}
    }});

    // update DOM with structured content from tool result
    // note: structured_content may only contain summary (fields stripped to
    // avoid model duplication). Only rebuild table rows when fields are present;
    // the server-side rendered rows are already correct.
    function applyToolResult(data) {{
      const summary = data.summary || {{}};
      const el = (id) => document.getElementById(id);
      el("stat-pci").textContent = summary.pci_fields ?? 0;
      el("stat-pii").textContent = summary.pii_fields ?? 0;
      el("stat-safe").textContent = summary.safe_fields ?? 0;
      el("stat-total").textContent = summary.total_fields ?? 0;
      el("recommendation").textContent = summary.recommendation || "";
      if (data._source) el("source-badge").textContent = data._source;

      // only rebuild table if fields are present in the notification
      if (!data.fields || data.fields.length === 0) return;

      const icons = {{ pci: "&#x1F534;", pii: "&#x1F7E1;", safe: "&#x1F7E2;" }};
      const tbody = el("field-rows");
      tbody.innerHTML = "";
      (data.fields || []).forEach(f => {{
        const sens = f.sensitivity || "safe";
        const enc = f.suggested_encryption || "none";
        let badge = "";
        if (enc === "deterministic") badge = '<span class="badge det">deterministic</span>';
        else if (enc === "standard") badge = '<span class="badge std">standard</span>';
        else badge = '<span class="badge safe">none</span>';
        const tr = document.createElement("tr");
        tr.className = sens;
        tr.innerHTML =
          '<td class="field-path"><code>' + (f.field_path || "") + '</code></td>' +
          '<td class="sensitivity">' + (icons[sens] || "") + ' ' + sens.toUpperCase() + '</td>' +
          '<td>' + badge + '</td>' +
          '<td class="reasoning">' + (f.reasoning || "") + '</td>';
        tbody.appendChild(tr);
      }});
    }}

    (async () => {{
      try {{
        const res = await mcpRequest("ui/initialize", {{
          protocolVersion: "2026-01-26",
          appCapabilities: {{}},
          appInfo: {{ name: "Schema Analysis Widget", version: "1.0.0" }}
        }});
        if (res && res.hostContext) {{
          applyHostContext(res.hostContext);
        }}
        mcpNotify("ui/notifications/initialized", {{}});
      }} catch (err) {{
        console.warn("MCP Apps init failed", err);
      }}
    }})();
  </script>
</body>
</html>"""
