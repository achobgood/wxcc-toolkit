# Webex Connect -- Quick Reference

## Flow Structure

```
Start (AI Agent Trigger) --> HTTP Request Node(s) --> End
```

Flow Outcomes is configured in **Flow Settings** (Settings icon → Flow Outcomes tab), not on the canvas.

## Variable Picker Format

| Context | Format |
|---------|--------|
| AI Agent entity | `$(n{nodeNumber}.aiAgent.{entity_name})` |
| Previous node output | `$(n{nodeNumber}.{variableName})` |

**NEVER type manually** -- always use the variable picker. Manually typed variables arrive empty at runtime.

<!-- SYNC: also update .claude/skills/build-scripted-fulfillment/reference.md (Standard Headers table) when changing this section -->
## Standard Headers (Supabase/PostgREST)

| Header | Value | When |
|--------|-------|------|
| `apikey` | `{anon_key}` | Always |
| `Authorization` | `Bearer {anon_key}` | Always (space before key required) |
| `Content-Type` | `application/json` | Always |
| `Accept` | `application/vnd.pgrst.object+json` | Single-object responses only |
| `Prefer` | `return=representation` | POST/PATCH only |

## Response Path Patterns

| Response Shape | Path | Use When |
|---------------|------|----------|
| Single object | `$.field_name` | Lookup by unique field (phone, email) |
| Array -- whole | `$` | Listing multiple records |
| Array -- first | `$[0].field_name` | Avoid if possible |

## Common URL Patterns

| Operation | Pattern |
|-----------|---------|
| Exact match | `/{table}?{col}=eq.$(n2.aiAgent.{entity})` |
| Fuzzy text | `/{table}?{col}=ilike.*$(n2.aiAgent.{entity})*` |
| Date range | `?{date_col}=gte.{start}&{date_col}=lte.{end}` |
| Sort + limit | `&order={col}.asc&limit=3` |
| Boolean filter | `?{col}=eq.false` |
| Hardcoded UUID | `?{col}=eq.{known-uuid}` |

Combine with `&`: `?location_id=eq.{uuid}&is_booked=eq.false&order=slot_time.asc&limit=3`

## Flow Outcomes Rules

Flow Outcomes is configured in **Flow Settings** (Settings icon → **Flow Outcomes** tab), not on the canvas.

1. Use **Enter key and value** mode -- NEVER Enter JSON mode (variables won't resolve)
2. Use the **variable picker** for values
3. Under **Last Execution Status**: **Notify AI Agent** is a radio button enabled by default — verify it is selected
4. Keys become the variable names the AI agent references

## POST/PATCH Bodies

- Set body type to **JSON**
- Use variable picker for values from AI agent or previous nodes
- Do NOT include auto-generated fields (IDs, confirmation_number, timestamps)
- Add `Prefer: return=representation` header to get the created/updated record back

## Multi-Node Chaining

1. Wire first node's **Success** output to second node's input
2. Reference first node's output: `$(n{nodeNumber}.{variableName})` (no `aiAgent` prefix)
3. Rename `id` in each node to avoid collisions (e.g., `customer_id`, `order_id`)

## Variable Naming

- Lowercase underscores only: `first_name`
- Allowed chars: alphabets, numbers, underscores, hyphens, spaces

## Prohibited Nodes

These risk exceeding the 30-second execution time limit in AI Agent flows:

- Delay
- Social Hour Check
- Receive (second instance)
- Call Workflow

## Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Variable arrives empty | Typed manually instead of picker | Use variable picker |
| 401 | Missing/malformed auth headers | Check `Bearer ` space |
| 400 | Wrong filter column | Verify column name matches DB |
| 406 | Single-object Accept + 0 rows | Remove Accept or fix filter |
| Outcomes show literal strings | Enter JSON mode | Switch to Enter key and value mode |
| Array breaks output vars | Accept header on array query | Remove Accept header |
| 30s timeout | Prohibited node in flow | Remove Delay/Social Hour Check/etc. |
| `id` collision | Multiple nodes both output `id` | Use consistent descriptive field names in sample JSON |
| Agent gets no data | Notify AI Agent radio button not selected | Verify selected in Flow Settings > Flow Outcomes |
