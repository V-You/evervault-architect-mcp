"""HTML widget renderers for MCP Apps.

Each function takes tool result data and returns a self-contained HTML string
for rendering in the VS Code chat panel via the ui:// resource protocol.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any


def _mcp_apps_js(widget_name: str, apply_tool_result_body: str) -> str:
    """Return the MCP Apps handshake + tool-result JS boilerplate.

    ``apply_tool_result_body`` is the function body for ``applyToolResult(data)``
    -- it receives the ``structuredContent`` dict and should update DOM elements.
    Uses placeholder replacement (not f-string) to keep JS braces literal.
    """
    template = """
    function escapeHtml(s) {
      return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;");
    }

    const pendingReqs = new Map();
    let msgId = 1;

    function mcpRequest(method, params) {
      return new Promise((resolve, reject) => {
        const id = msgId++;
        pendingReqs.set(id, { resolve, reject });
        window.parent.postMessage({ jsonrpc: "2.0", id, method, params: params || {} }, "*");
      });
    }

    function mcpNotify(method, params) {
      window.parent.postMessage({ jsonrpc: "2.0", method, params: params || {} }, "*");
    }

    function applyHostContext(ctx) {
      if (ctx && ctx.styles && ctx.styles.variables) {
        for (const [k, v] of Object.entries(ctx.styles.variables)) {
          document.documentElement.style.setProperty(k, v);
        }
      }
      if (ctx && ctx.theme) {
        document.documentElement.style.colorScheme = ctx.theme;
      }
    }

    window.addEventListener("message", (e) => {
      const data = e.data;
      if (!data || data.jsonrpc !== "2.0") return;

      if (data.id !== undefined && (data.result !== undefined || data.error)) {
        const p = pendingReqs.get(data.id);
        if (p) {
          pendingReqs.delete(data.id);
          if (data.error) p.reject(new Error(data.error.message));
          else p.resolve(data.result);
        }
        return;
      }

      if (data.method === "ui/notifications/host-context-changed") {
        applyHostContext(data.params);
      }

      if (data.method === "ui/notifications/tool-result" && data.params) {
        const sc = data.params.structuredContent;
        if (sc) {
          applyToolResult(sc);
        }
      }
    });

    function applyToolResult(data) {
      __APPLY_BODY__
    }

    (async () => {
      try {
        const res = await mcpRequest("ui/initialize", {
          protocolVersion: "2026-01-26",
          appCapabilities: {},
          appInfo: { name: "__WIDGET_NAME__", version: "1.0.0" }
        });
        if (res && res.hostContext) {
          applyHostContext(res.hostContext);
        }
        mcpNotify("ui/notifications/initialized", {});
      } catch (err) {
        console.warn("MCP Apps init failed", err);
      }
    })();"""
    return template.replace("__WIDGET_NAME__", widget_name).replace(
        "__APPLY_BODY__", apply_tool_result_body
    )


def _base_css(source: str) -> str:
    """Return common CSS for VS Code widget theming."""
    badge_bg = "#2d5a2d" if source == "live" else "#5a4a1a" if source == "mock" else "#2a3a5a"
    badge_fg = "#4ec94e" if source == "live" else "#e6c84e" if source == "mock" else "#7aa3e6"
    return f"""  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
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
  .title {{ font-size: 14px; font-weight: 600; }}
  .source-badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: {badge_bg};
    color: {badge_fg};
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
  .stat-value {{ font-size: 20px; font-weight: 700; }}
  .stat-label {{ font-size: 11px; opacity: 0.7; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; }}
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
  }}"""


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


def render_encrypt_result(data: dict[str, Any]) -> str:
    """Render ev_encrypt results as an interactive HTML widget."""
    encrypted = data.get("encrypted", {})
    source = data.get("_source", "unknown")

    # classify fields
    encrypted_count = 0
    unchanged_count = 0
    field_rows = ""
    for key, value in encrypted.items():
        val_str = str(value)
        is_enc = val_str.startswith("ev:")
        if is_enc:
            encrypted_count += 1
            status_icon = "&#x1F512;"  # lock
            status_text = "ENCRYPTED"
            status_class = "encrypted"
            # truncate long tokens for display
            if len(val_str) > 40:
                display_val = val_str[:20] + "..." + val_str[-12:]
            else:
                display_val = val_str
        else:
            unchanged_count += 1
            status_icon = "&#x2796;"  # minus
            status_text = "UNCHANGED"
            status_class = "unchanged"
            display_val = val_str

        field_rows += f"""
        <tr class="{status_class}">
            <td class="field-name"><code>{key}</code></td>
            <td class="status">{status_icon} {status_text}</td>
            <td class="value"><code>{display_val}</code></td>
        </tr>"""

    total = encrypted_count + unchanged_count

    js_body = """
      const enc = data.encrypted || {};
      const el = (id) => document.getElementById(id);
      let encCount = 0, uncCount = 0;
      const rows = [];
      for (const [key, val] of Object.entries(enc)) {
        const v = String(val);
        const isEnc = v.startsWith("ev:");
        if (isEnc) encCount++; else uncCount++;
        const icon = isEnc ? "&#x1F512;" : "&#x2796;";
        const label = isEnc ? "ENCRYPTED" : "UNCHANGED";
        const cls = isEnc ? "encrypted" : "unchanged";
        const display = (isEnc && v.length > 40) ? v.slice(0, 20) + "..." + v.slice(-12) : v;
        rows.push('<tr class="' + cls + '">' +
          '<td class="field-name"><code>' + key + '</code></td>' +
          '<td class="status">' + icon + ' ' + label + '</td>' +
          '<td class="value"><code>' + display + '</code></td></tr>');
      }
      el("stat-encrypted").textContent = encCount;
      el("stat-unchanged").textContent = uncCount;
      el("stat-total").textContent = encCount + uncCount;
      if (data._source) el("source-badge").textContent = data._source;
      if (rows.length > 0) el("field-rows").innerHTML = rows.join("");
    """

    js_code = _mcp_apps_js("Encrypt Result Widget", js_body)

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
  .title {{ font-size: 14px; font-weight: 600; }}
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
  .stat.enc .stat-value {{ color: #4c4; }}
  .stat.unc .stat-value {{ color: #888; }}
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
  tr.encrypted {{ background: rgba(68, 204, 68, 0.06); }}
  tr.unchanged {{ background: transparent; }}
  .field-name code, .value code {{
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
  }}
  .value code {{
    word-break: break-all;
  }}
  .status {{ white-space: nowrap; }}
</style>
</head>
<body>
  <div class="header">
    <span class="title">Encryption result</span>
    <span class="source-badge" id="source-badge">{source}</span>
  </div>
  <div class="stats">
    <div class="stat enc">
      <div class="stat-value" id="stat-encrypted">{encrypted_count}</div>
      <div class="stat-label">Encrypted</div>
    </div>
    <div class="stat unc">
      <div class="stat-value" id="stat-unchanged">{unchanged_count}</div>
      <div class="stat-label">Unchanged</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-total">{total}</div>
      <div class="stat-label">Total</div>
    </div>
  </div>
  <table>
    <thead>
      <tr><th>Field</th><th>Status</th><th>Value</th></tr>
    </thead>
    <tbody id="field-rows">{field_rows}
    </tbody>
  </table>
  <script>
    {js_code}
  </script>
</body>
</html>"""


def render_inspect_result(data: dict[str, Any]) -> str:
    """Render ev_inspect results as an interactive HTML widget."""
    inspections = data.get("inspections", [])
    source = data.get("_source", "unknown")

    # collect stats
    token_count = len(inspections)
    categories = set()
    has_roles = False
    for insp in inspections:
        cat = insp.get("category")
        if cat:
            categories.add(cat)
        if insp.get("role"):
            has_roles = True
    categories_count = len(categories)

    field_rows = ""
    for i, insp in enumerate(inspections, 1):
        dtype = insp.get("type", "unknown")
        category = insp.get("category") or "---"
        role = insp.get("role") or "---"
        enc_at = insp.get("encryptedAt")
        fingerprint = insp.get("fingerprint", "")

        # format timestamp in server-side render
        if enc_at:
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(enc_at / 1000, tz=timezone.utc)
            enc_at_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        else:
            enc_at_str = "---"

        # truncate fingerprint
        fp_display = fingerprint[:16] + "..." if len(fingerprint) > 16 else fingerprint

        cat_badge = ""
        if category != "---":
            cat_badge = f'<span class="badge cat">{category}</span>'
        else:
            cat_badge = '<span class="badge none">---</span>'

        role_badge = ""
        if role != "---":
            role_badge = f'<span class="badge role">{role}</span>'
        else:
            role_badge = '<span class="badge none">---</span>'

        field_rows += f"""
        <tr>
            <td class="idx">{i}</td>
            <td><code>{dtype}</code></td>
            <td>{cat_badge}</td>
            <td>{role_badge}</td>
            <td class="timestamp">{enc_at_str}</td>
            <td class="fingerprint"><code>{fp_display}</code></td>
        </tr>"""

    js_body = """
      const inspections = data.inspections || [];
      const el = (id) => document.getElementById(id);
      el("stat-tokens").textContent = inspections.length;
      const cats = new Set();
      let hasRoles = false;
      inspections.forEach(i => {
        if (i.category) cats.add(i.category);
        if (i.role) hasRoles = true;
      });
      el("stat-categories").textContent = cats.size;
      el("stat-roles").textContent = hasRoles ? "Yes" : "No";
      if (data._source) el("source-badge").textContent = data._source;

      if (inspections.length === 0) return;
      const rows = [];
      inspections.forEach((insp, idx) => {
        const dtype = insp.type || "unknown";
        const cat = insp.category || "---";
        const role = insp.role || "---";
        const fp = insp.fingerprint || "";
        const fpShort = fp.length > 16 ? fp.slice(0, 16) + "..." : fp;
        let encAt = "---";
        if (insp.encryptedAt) {
          const d = new Date(insp.encryptedAt);
          encAt = d.toISOString().replace("T", " ").slice(0, 16) + " UTC";
        }
        const catBadge = cat !== "---"
          ? '<span class="badge cat">' + cat + '</span>'
          : '<span class="badge none">---</span>';
        const roleBadge = role !== "---"
          ? '<span class="badge role">' + role + '</span>'
          : '<span class="badge none">---</span>';
        rows.push('<tr>' +
          '<td class="idx">' + (idx + 1) + '</td>' +
          '<td><code>' + dtype + '</code></td>' +
          '<td>' + catBadge + '</td>' +
          '<td>' + roleBadge + '</td>' +
          '<td class="timestamp">' + encAt + '</td>' +
          '<td class="fingerprint"><code>' + fpShort + '</code></td></tr>');
      });
      el("field-rows").innerHTML = rows.join("");
    """

    js_code = _mcp_apps_js("Token Inspection Widget", js_body)

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
  .title {{ font-size: 14px; font-weight: 600; }}
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
  .stat.tokens .stat-value {{ color: #7aa3e6; }}
  .stat.cats .stat-value {{ color: #c9a3e6; }}
  .stat.roles .stat-value {{ color: #e6c84e; }}
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
  .idx {{ opacity: 0.5; width: 30px; }}
  .timestamp {{ white-space: nowrap; font-size: 12px; }}
  .fingerprint code {{
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 11px;
    opacity: 0.7;
  }}
  .badge {{
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 500;
  }}
  .badge.cat {{ background: #2a2a3a; color: #c9a3e6; }}
  .badge.role {{ background: #3a3a1a; color: #e6c84e; }}
  .badge.none {{ background: transparent; opacity: 0.4; }}
</style>
</head>
<body>
  <div class="header">
    <span class="title">Token inspection</span>
    <span class="source-badge" id="source-badge">{source}</span>
  </div>
  <div class="stats">
    <div class="stat tokens">
      <div class="stat-value" id="stat-tokens">{token_count}</div>
      <div class="stat-label">Tokens</div>
    </div>
    <div class="stat cats">
      <div class="stat-value" id="stat-categories">{categories_count}</div>
      <div class="stat-label">Categories</div>
    </div>
    <div class="stat roles">
      <div class="stat-value" id="stat-roles">{"Yes" if has_roles else "No"}</div>
      <div class="stat-label">Roles used</div>
    </div>
  </div>
  <table>
    <thead>
      <tr><th>#</th><th>Type</th><th>Category</th><th>Role</th><th>Encrypted at</th><th>Fingerprint</th></tr>
    </thead>
    <tbody id="field-rows">{field_rows}
    </tbody>
  </table>
  <script>
    {js_code}
  </script>
</body>
</html>"""


def render_docs_panel(data: dict[str, Any]) -> str:
    """Render ev_docs_query results as a documentation panel widget."""
    question = data.get("question", "")
    documentation = data.get("documentation", "")
    sources = data.get("sources", [])
    source = data.get("_source", "local")

    source_links_html = ""
    for s in sources:
        title = escape(s.get("title", ""))
        url = escape(s.get("url", ""))
        if title and url:
            source_links_html += f'<li><a href="{url}" target="_blank">{title}</a></li>'

    js_body = """
      const el = (id) => document.getElementById(id);
      if (data.question) {
        el("question").textContent = data.question;
        el("question").style.display = "";
      }
      if (data.documentation) {
        el("doc-content").textContent = data.documentation;
        el("doc-content").style.display = "";
        const es = el("empty-state");
        if (es) es.style.display = "none";
      }
      if (data._source) el("source-badge").textContent = data._source;
      const ul = el("source-links");
      if (ul && data.sources && data.sources.length > 0) {
        ul.innerHTML = "";
        data.sources.forEach(s => {
          if (s.title && s.url) {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = s.url;
            a.target = "_blank";
            a.textContent = s.title;
            li.appendChild(a);
            ul.appendChild(li);
          }
        });
        ul.style.display = "";
      }
    """

    js_code = _mcp_apps_js("Documentation Widget", js_body)
    has_data = bool(question or documentation)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<style>
{_base_css(source)}
  .question {{
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 10px;
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
  }}
  .doc-content {{
    white-space: pre-wrap;
    font-family: inherit;
    font-size: 12px;
    line-height: 1.5;
    padding: 10px 12px;
    border-radius: 6px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
    max-height: 400px;
    overflow-y: auto;
    margin-bottom: 12px;
  }}
  .sources {{
    list-style: none;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .sources li a {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 11px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
    color: var(--vscode-textLink-foreground, #7aa3e6);
    text-decoration: none;
  }}
  .sources li a:hover {{ text-decoration: underline; }}
  .empty-state {{
    text-align: center;
    opacity: 0.5;
    padding: 20px;
    font-style: italic;
  }}
</style>
</head>
<body>
  <div class="header">
    <span class="title">Documentation</span>
    <span class="source-badge" id="source-badge">{source}</span>
  </div>
  <div class="question" id="question" {"" if has_data else 'style="display:none"'}>{escape(question)}</div>
  <pre class="doc-content" id="doc-content" {"" if has_data else 'style="display:none"'}>{escape(documentation)}</pre>
  <ul class="sources" id="source-links" {"" if source_links_html else 'style="display:none"'}>{source_links_html}</ul>
  {"" if has_data else '<p class="empty-state" id="empty-state">No documentation query yet -- run ev_docs_query to see results.</p>'}
  <script>
    {js_code}
  </script>
</body>
</html>"""


def render_relay_config(data: dict[str, Any]) -> str:
    """Render ev_relay_create results as a relay configuration widget."""
    relay = data.get("relay", {})
    source = data.get("_source", "unknown")

    relay_id = relay.get("id", "---")
    domain = relay.get("destinationDomain", "---")
    subdomain = relay.get("subdomain", "---")
    encrypt_empty = relay.get("encryptEmptyStrings", False)
    routes = relay.get("routes", [])

    route_rows = ""
    for r in routes:
        method = escape(r.get("method") or "*")
        path = escape(r.get("path", ""))
        req_actions = ", ".join(
            escape(a.get("action", "")) for a in r.get("request", [])
        ) or "---"
        resp_actions = ", ".join(
            escape(a.get("action", "")) for a in r.get("response", [])
        ) or "---"
        route_rows += (
            f'<tr><td><code>{method}</code></td><td><code>{path}</code></td>'
            f'<td>{req_actions}</td><td>{resp_actions}</td></tr>'
        )

    js_body = """
      const el = (id) => document.getElementById(id);
      const relay = data.relay || data;
      el("relay-id").textContent = relay.id || "---";
      el("relay-domain").textContent = relay.destinationDomain || "---";
      el("relay-subdomain").textContent = relay.subdomain || "---";
      el("encrypt-empty").textContent = relay.encryptEmptyStrings ? "Yes" : "No";
      if (data._source) el("source-badge").textContent = data._source;
      const routes = relay.routes || [];
      el("stat-routes").textContent = routes.length;
      const tbody = el("route-rows");
      if (routes.length > 0) {
        tbody.innerHTML = "";
        routes.forEach(r => {
          const method = escapeHtml(r.method || "*");
          const path = escapeHtml(r.path || "");
          const req = (r.request || []).map(a => escapeHtml(a.action || "")).join(", ") || "---";
          const resp = (r.response || []).map(a => escapeHtml(a.action || "")).join(", ") || "---";
          tbody.innerHTML += '<tr><td><code>' + method + '</code></td>' +
            '<td><code>' + path + '</code></td>' +
            '<td>' + req + '</td><td>' + resp + '</td></tr>';
        });
      }
      const es = el("empty-state");
      if (es && relay.id) es.style.display = "none";
    """

    js_code = _mcp_apps_js("Relay Config Widget", js_body)
    has_data = bool(relay.get("id"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<style>
{_base_css(source)}
  .summary {{
    margin-bottom: 12px;
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
  }}
  .summary-row {{
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
    font-size: 12px;
  }}
  .summary-label {{ opacity: 0.6; }}
  .subdomain-display {{
    margin-bottom: 12px;
    padding: 10px 12px;
    border-radius: 6px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
    border-left: 3px solid #4ec94e;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
    word-break: break-all;
  }}
  .subdomain-label {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 11px;
    opacity: 0.6;
    margin-bottom: 4px;
  }}
  code {{ font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 12px; }}
  .footnote {{ font-size: 11px; opacity: 0.5; margin-top: 8px; }}
  .empty-state {{ text-align: center; opacity: 0.5; padding: 20px; font-style: italic; }}
</style>
</head>
<body>
  <div class="header">
    <span class="title">Relay created</span>
    <span class="source-badge" id="source-badge">{source}</span>
  </div>
  <div class="summary">
    <div class="summary-row">
      <span class="summary-label">Relay ID</span>
      <span id="relay-id">{escape(relay_id)}</span>
    </div>
    <div class="summary-row">
      <span class="summary-label">Destination</span>
      <span id="relay-domain">{escape(domain)}</span>
    </div>
  </div>
  <div class="subdomain-display">
    <div class="subdomain-label">Relay subdomain</div>
    <span id="relay-subdomain">{escape(subdomain)}</span>
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-value" id="stat-routes">{len(routes)}</div>
      <div class="stat-label">Routes</div>
    </div>
  </div>
  <table>
    <thead>
      <tr><th>Method</th><th>Path</th><th>Request</th><th>Response</th></tr>
    </thead>
    <tbody id="route-rows">{route_rows}
    </tbody>
  </table>
  <div class="footnote">encryptEmptyStrings: <span id="encrypt-empty">{"Yes" if encrypt_empty else "No"}</span></div>
  {"" if has_data else '<p class="empty-state" id="empty-state">No relay created yet -- run ev_relay_create to see results.</p>'}
  <script>
    {js_code}
  </script>
</body>
</html>"""


def render_relay_dashboard(data: dict[str, Any]) -> str:
    """Render ev_relay_list results as a relay dashboard widget."""
    relays = data.get("relays", [])
    source = data.get("_source", "unknown")

    relay_count = len(relays)
    total_routes = sum(len(r.get("routes", [])) for r in relays)

    relay_rows = ""
    for relay in relays:
        rid = escape(relay.get("id", ""))
        domain = escape(relay.get("destinationDomain", ""))
        subdomain = relay.get("subdomain", "")
        sub_display = escape(subdomain[:30] + "..." if len(subdomain) > 30 else subdomain)
        routes = relay.get("routes", [])
        route_count = len(routes)
        actions: dict[str, int] = {}
        for rt in routes:
            for a in rt.get("request", []):
                act = a.get("action", "")
                if act:
                    actions[act] = actions.get(act, 0) + 1
            for a in rt.get("response", []):
                act = a.get("action", "")
                if act:
                    actions[act] = actions.get(act, 0) + 1
        actions_str = escape(", ".join(f"{a}: {c}" for a, c in actions.items())) or "---"
        relay_rows += (
            f'<tr><td><code>{rid}</code></td><td>{domain}</td>'
            f'<td class="subdomain" title="{escape(subdomain)}">'
            f'<code>{sub_display}</code></td>'
            f'<td>{route_count}</td><td>{actions_str}</td></tr>'
        )

    js_body = """
      const el = (id) => document.getElementById(id);
      const relays = data.relays || [];
      el("stat-relays").textContent = relays.length;
      let totalRoutes = 0;
      relays.forEach(r => { totalRoutes += (r.routes || []).length; });
      el("stat-routes").textContent = totalRoutes;
      if (data._source) el("source-badge").textContent = data._source;
      const tbody = el("relay-rows");
      if (relays.length > 0) {
        tbody.innerHTML = "";
        relays.forEach(relay => {
          const rid = escapeHtml(relay.id || "");
          const domain = escapeHtml(relay.destinationDomain || "");
          const sub = relay.subdomain || "";
          const subDisplay = escapeHtml(sub.length > 30 ? sub.slice(0, 30) + "..." : sub);
          const routes = relay.routes || [];
          const actions = {};
          routes.forEach(rt => {
            (rt.request || []).forEach(a => { if (a.action) actions[a.action] = (actions[a.action] || 0) + 1; });
            (rt.response || []).forEach(a => { if (a.action) actions[a.action] = (actions[a.action] || 0) + 1; });
          });
          const actStr = escapeHtml(Object.entries(actions).map(([a,c]) => a + ": " + c).join(", ")) || "---";
          tbody.innerHTML += '<tr><td><code>' + rid + '</code></td>' +
            '<td>' + domain + '</td>' +
            '<td class="subdomain" title="' + escapeHtml(sub) + '"><code>' + subDisplay + '</code></td>' +
            '<td>' + routes.length + '</td><td>' + actStr + '</td></tr>';
        });
      }
      const es = el("empty-state");
      if (es && relays.length > 0) es.style.display = "none";
    """

    js_code = _mcp_apps_js("Relay Dashboard Widget", js_body)
    has_data = relay_count > 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<style>
{_base_css(source)}
  .subdomain code {{ font-size: 11px; opacity: 0.7; }}
  code {{ font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 12px; }}
  .empty-state {{ text-align: center; opacity: 0.5; padding: 20px; font-style: italic; }}
</style>
</head>
<body>
  <div class="header">
    <span class="title">Relay dashboard</span>
    <span class="source-badge" id="source-badge">{source}</span>
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-value" id="stat-relays">{relay_count}</div>
      <div class="stat-label">Relays</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-routes">{total_routes}</div>
      <div class="stat-label">Total routes</div>
    </div>
  </div>
  <table>
    <thead>
      <tr><th>ID</th><th>Destination</th><th>Subdomain</th><th>Routes</th><th>Actions</th></tr>
    </thead>
    <tbody id="relay-rows">{relay_rows}
    </tbody>
  </table>
  {"" if has_data else '<p class="empty-state" id="empty-state">No relays found -- run ev_relay_list to see results.</p>'}
  <script>
    {js_code}
  </script>
</body>
</html>"""


def render_function_run(data: dict[str, Any]) -> str:
    """Render ev_function_run results as a function execution widget."""
    func_name = data.get("function_name", "---")
    status = data.get("status", "unknown")
    exec_time = data.get("execution_time_ms")
    result = data.get("result", {})
    source = data.get("_source", "unknown")

    status_ok = status == "success"

    if exec_time is not None:
        time_color = "#4ec94e" if exec_time < 500 else "#e6c84e" if exec_time < 2000 else "#f44"
        time_display = f"{exec_time}ms"
    else:
        time_color = "#888"
        time_display = "---"

    result_json = escape(json.dumps(result, indent=2)) if result else ""

    js_body = """
      const el = (id) => document.getElementById(id);
      el("func-name").textContent = data.function_name || "---";
      const status = data.status || "unknown";
      const badge = el("status-badge");
      badge.textContent = status;
      badge.className = "status-badge " + (status === "success" ? "ok" : "err");
      const time = data.execution_time_ms;
      const timeEl = el("exec-time");
      if (time !== undefined && time !== null) {
        timeEl.textContent = time + "ms";
        timeEl.style.color = time < 500 ? "#4ec94e" : time < 2000 ? "#e6c84e" : "#f44";
      } else {
        timeEl.textContent = "---";
      }
      if (data._source) el("source-badge").textContent = data._source;
      const pre = el("result-json");
      if (data.result && Object.keys(data.result).length > 0) {
        pre.textContent = JSON.stringify(data.result, null, 2);
        pre.style.display = "";
      }
      const es = el("empty-state");
      if (es && data.function_name) es.style.display = "none";
    """

    js_code = _mcp_apps_js("Function Run Widget", js_body)
    has_data = func_name != "---"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<style>
{_base_css(source)}
  .summary {{
    margin-bottom: 12px;
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .func-name {{
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 13px;
    font-weight: 600;
  }}
  .status-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 500;
  }}
  .status-badge.ok {{ background: #2d5a2d; color: #4ec94e; }}
  .status-badge.err {{ background: #5a2d2d; color: #f44; }}
  .exec-time {{
    font-size: 13px;
    font-weight: 600;
  }}
  .result-json {{
    white-space: pre-wrap;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
    line-height: 1.4;
    padding: 10px 12px;
    border-radius: 6px;
    background: var(--vscode-editor-inactiveSelectionBackground, #2a2a2a);
    max-height: 300px;
    overflow-y: auto;
  }}
  .empty-state {{ text-align: center; opacity: 0.5; padding: 20px; font-style: italic; }}
</style>
</head>
<body>
  <div class="header">
    <span class="title">Function execution</span>
    <span class="source-badge" id="source-badge">{source}</span>
  </div>
  <div class="summary">
    <span class="func-name" id="func-name">{escape(func_name)}</span>
    <span class="status-badge {"ok" if status_ok else "err"}" id="status-badge">{escape(status)}</span>
    <span class="exec-time" id="exec-time" style="color: {time_color}">{time_display}</span>
  </div>
  <pre class="result-json" id="result-json" {"" if result_json else 'style="display:none"'}>{result_json}</pre>
  {"" if has_data else '<p class="empty-state" id="empty-state">No function executed yet -- run ev_function_run to see results.</p>'}
  <script>
    {js_code}
  </script>
</body>
</html>"""
