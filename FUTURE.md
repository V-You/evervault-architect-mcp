# Future improvements

## 2026-03-05 -- from PRD widget-wiring QA

### Preserve `_fallback_reason` in inline demo-mode handling

When `@with_fallback` is removed (PRD section 3 step 6), the current fallback path includes `_fallback_reason` via `make_fallback_envelope()` in `errors.py`. The inline pattern used by `ev_encrypt` and `ev_inspect` does not preserve this field. Add `_fallback_reason` to the `ToolResult` structured_content when a tool falls back to a fixture, so demo/debug observability is maintained.

### Strengthen renderer smoke-check acceptance criterion

The current criterion (`python -c "from evervault_mcp.widgets import ...; print('OK')"`) only checks that renderers import without error. It does not execute them. Replace with a check that calls each renderer with both empty-state and sample payloads and verifies valid HTML output. Should cover all 7 renderers, not just the 4 new ones.

### Add acceptance criterion for SKILL file updates

Section 4 (anti-duplication strategy) references SKILL behavioral guidance, but no acceptance criterion enforces that `.github/skills/*/SKILL.md` files are updated when new widgets are added. Add a checklist item to verify SKILL files reference all widget-enabled tools appropriately.
