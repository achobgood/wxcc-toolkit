# Webex Connect Flows Playbook

<!-- ref-tag: connect-flows-v1 -->

## Overview

This playbook covers how to build Webex Connect flows that back AI agent actions. Each action in AI Agent Studio maps to exactly one Connect flow.

---

## 1. Flow Structure for AI Agent Actions

Each action flow follows this pattern:

```
Start (AI Agent Trigger) → HTTP Request Node(s) → End
```

Flow Outcomes are configured in **Flow Settings** (not a node on the canvas).

### Required Nodes
- **Start node** (always first): triggers on the AI Agent event
- **HTTP Request node(s)**: calls Supabase PostgREST API
- **End node**: terminates the flow

### Prohibited Nodes in AI Agent Flows
These nodes risk exceeding the 30-second execution time limit and break the agent:
- Delay
- Social Hour Check
- Receive
- Call Workflow

---

## 2. Start Node Configuration

The **Start** node is always the first node in a new flow — it is already on the canvas when you create the flow.

1. Click the **Start** node to open its configuration
2. Set **Trigger category** to: **AI Agent**
3. The event auto-populates as "Trigger from AI Agent to initiate flow" — no manual entry needed
4. In the **Provide sample JSON** field, paste a sample payload with one key per slot entity the action declares, then click **Parse** to register the variables

---

## 3. HTTP Request Node — Supabase GET

### URL Format
```
https://{project-ref}.supabase.co/rest/v1/{table}?{filter}
```

Use the **variable picker** (not manual typing) to insert AI Agent variables into the URL:
```
...?phone_number=eq.$(n2.aiAgent.phone_number)
```
Node numbers change based on flow layout — always use the picker to get the correct reference. The `aiAgent` segment in the variable path is not documented in official docs; use the picker to confirm the exact format.

### Headers (standard set)
| Header | Value |
|--------|-------|
| `apikey` | `{anon_key}` |
| `Authorization` | `Bearer {anon_key}` (space before key is required) |
| `Content-Type` | `application/json` |
| `Accept` | `application/vnd.pgrst.object+json` ← **omit for array responses** |

### Output Variables Tab
1. Click **Import from Sample**, paste a sample JSON response into the Data Parser dialog, click **Parse**, select the key paths to extract under "Select key paths to be extracted", then click **Import** — rows auto-generate
2. Renaming output variables after parsing is not documented in official docs; use consistent field names in your sample JSON to avoid naming conflicts across nodes
3. Response path format (not documented in official docs — the UI uses key-path selection):
   - Single object (with Accept header): `$.field_name`
   - Array response (no Accept header): `$[0].field_name` for first element, or `$` for whole array

---

## 4. HTTP Request Node — Supabase POST

For create/update operations:

### Method: POST
### URL: `https://{project-ref}.supabase.co/rest/v1/{table}`

### Additional Headers
Add on top of the standard set:
```
Prefer: return=representation
```
This tells PostgREST to return the created record so you can capture the generated ID and confirmation number.

### Body
- Set body type to **JSON**
- Use variable picker to insert values from previous HTTP nodes or AI agent entities:
```json
{
  "patient_id": "$(n3.patient_id)",
  "location_id": "{known-uuid}",
  "test_id": "$(n2.aiAgent.test_id)",
  "scheduled_at": "$(n2.aiAgent.scheduled_at)",
  "status": "scheduled"
}
```

---

## 5. Chaining Multiple HTTP Nodes

When an action requires multiple API calls (e.g., GET patient_id then POST appointment):

1. Add a second HTTP Request node after the first
2. Wire first node's **Success** output → second node's input
3. Reference output variables from first node in second node's URL or body using the picker
4. Variable format from a previous node: `$(n{nodeNumber}.{variableName})`

---

## 6. Flow Outcomes Configuration

Flow Outcomes is **not a node**. It is configured in **Flow Settings** (Settings icon → **Flow Outcomes** tab). Wire the last HTTP node to an **End** node.

**Critical:** Always use **Enter key and value** mode, not Enter JSON mode. Enter JSON mode does not resolve variables.

### Configuration Steps
1. Click the **Settings** icon to open Flow Settings
2. Go to the **Flow Outcomes** tab
3. Under **Last Execution Status**: **Notify AI Agent** is a radio button that is enabled by default for flows with an AI Agent Start node trigger — verify it is selected
4. Add one row per variable to return to the AI agent using **Enter key and value** mode:
   - Key: the name as the AI agent will reference it (e.g., `patient_first_name`)
   - Value: use variable picker to select from HTTP node output

---

## 7. Configure AI Agent Event (Sample JSON)

Every action requires a sample JSON payload registered in the **Webex Connect** flow's **Start node** (in the "Provide sample JSON" field of the AI Agent trigger configuration). This tells Connect what shape of data to expect from the agent.

Format example for `lookup_patient`:
```json
{
  "phone_number": "5551234567"
}
```

One key per slot entity the action declares. Use realistic example values.

---

## 8. Variable Naming Rules

Connect variable names allow: **alphabets, numbers, underscores, hyphens, spaces**

Use lowercase underscores consistently:
- `patient_first_name` ✅
- `patientFirstName` — avoid
- `patient-first-name` — allowed but inconsistent

---

## 9. Common URL Patterns

| Operation | URL Pattern |
|-----------|-------------|
| Lookup by phone | `/{table}?phone_number=eq.$(n2.aiAgent.phone_number)` |
| Fuzzy search by name | `/{table}?name=ilike.*$(n2.aiAgent.search_term)*` |
| Filter by date range | `/{table}?date_col=gte.$(n2.aiAgent.date)T00:00:00&date_col=lte.$(n2.aiAgent.date)T23:59:59` |
| Filter + limit | `&order=date_col.asc&limit=3` |
| Hardcoded UUID filter | `/{table}?location_id=eq.{known-uuid}` |

---

## 10. Testing a Flow

Before wiring it to an AI agent action:

1. Use **curl** to test the raw Supabase URL with the same headers
2. Verify the response shape matches what your output variables expect
3. In Connect, use **Test Flow** (if available) or trigger via a test AI agent session

---

## 11. Known Gotchas

| Issue | Fix |
|-------|-----|
| Variable arrives empty in URL | Variable not substituted — use variable picker, never type manually |
| `401` error | Auth headers missing or `Bearer ` space missing before key |
| `400` error | Wrong filter column (e.g., `id=eq.` when you need `phone_number=eq.`) |
| `406` error | Single-object Accept header used but query returned 0 rows |
| Flow Outcomes variables show as literal strings | Switched to Enter JSON mode — switch back to Enter key and value mode (observed behavior; not documented) |
| Array response breaks output variables | Remove `Accept: application/vnd.pgrst.object+json` header |
| 30-second timeout in agent flow | Prohibited node in use (Delay, Social Hour Check, Receive, Call Workflow) — these risk exceeding the 30-second execution time limit |
