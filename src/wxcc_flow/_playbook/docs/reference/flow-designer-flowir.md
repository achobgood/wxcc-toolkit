<!-- ref-tag: fd-flowir-v2 -->

# Flow Designer FlowIR Reference

FlowIR is Cisco's intermediate representation format for Flow Designer flows. It is the documented, API-supported format for programmatic flow building via the v2 REST API and MCP server. FlowIR is NOT the proprietary export JSON — the server resolves FlowIR into the full internal format (activity UUIDs, connector IDs, event spec IDs, diagram coordinates) automatically.

## 1. REST API Endpoints

Base URL: `https://flow-store.produs1.ciscoccservice.com/flow-store`
Auth: `Authorization: Bearer <token>` header

> ⚠️ **Path structure (verified live on produs1, 2026-07-11):** the `v2` segment comes **after**
> `project/{projectId}`, NOT before `{orgId}`. The `/v2/{orgId}/project/{projectId}/...` form 500s on
> prod (unrouted path). If these ever 500/404, re-pull the live contract `GET {base}/v3/api-docs` and diff.
> "FlowIR" is our coined term; Cisco's schema is **FlowV2** (FDL 2.0).

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/{orgId}/project/{projectId}/v2/flows:import?overwrite=` | Create flow from FlowV2 → `201`, returns `{"flow":{...}}` |
| POST | `/{orgId}/project/{projectId}/v2/flows:validate` | Dry-run validate FlowV2 (no save) → `{valid, errors, warnings}` |
| GET | `/{orgId}/project/{projectId}/v2/flows/{flowId}` | Read flow as FlowV2 (use this for export/draft) |
| POST | `/{orgId}/project/{projectId}/v2/flows/{flowId}?expectedVersion=N` | Save draft from FlowV2 (optimistic lock; **no `/draft` suffix**) |
| GET | `/{orgId}/project/{projectId}/v2/flows/{flowId}:validate` | Validate a persisted flow → `{valid, results}` |
| GET | `/{orgId}/project/{projectId}/v2/activities` | List activity definitions (flat list, keyed by `activityName`) |
| GET | `/{orgId}/project/{projectId}/v2/activities/{name}` | Describe one activity |
| GET | `/{orgId}/project/{projectId}/v2/activities/{name}/inputs/{input}/choices` | Dropdown values |

The `orgId` and `projectId` are required in all paths. Resolve `projectId` via `GET /{orgId}/project`.
Dead route: `GET .../v2/flows/{flowId}:export` returns `400 "Invalid flowId"` even on published flows —
use the read endpoint (`GET .../v2/flows/{flowId}`) instead. There is no `.../activities/{name}/schema`
endpoint on prod.

## 2. FlowIR Structure

```json
{
  "name": "Flow_Name",
  "flowType": "FLOW",
  "description": "...",
  "variables": [],
  "nodes": [],
  "edges": [],
  "eventFlows": {}
}
```

### flowType Values

| Value | Usage |
|-------|-------|
| `FLOW` | Main flow (inbound voice, etc.) |
| `SUBFLOW` | Reusable subflow |

## 3. Variables

```json
{
  "name": "varName",
  "type": "STRING",
  "value": "",
  "isReportable": false,
  "isCAD": false,
  "isAgentEditable": false,
  "isSecure": false,
  "isExternalized": false,
  "desktopLabel": "",
  "description": ""
}
```

| Field | Required | Values |
|-------|----------|--------|
| `name` | Yes | Variable name |
| `type` | Yes | `STRING`, `INTEGER`, `BOOLEAN` |
| `value` | Yes | Default value (string, even for INTEGER — use `"0"`) |
| `isReportable` | No | Whether variable appears in Analyzer |
| `isCAD` | No | Call-associated data |
| `isAgentEditable` | No | Agent can modify on desktop |
| `isSecure` | No | Encrypted storage |
| `isExternalized` | No | Externalized to global scope |
| `desktopLabel` | No | Label shown to agent on desktop |
| `source` | Conditional | `"GLOBAL_TM"` for org-wide global variables. Omit for flow-local variables. |
| `id` | Conditional | UUID of the global variable (from `wxcc-flow global-vars -o json`). Required when `source` is `"GLOBAL_TM"`. Omit for flow-local variables. |
| `overwrite` | No | Whether flow can overwrite the global variable's default value |

### Global Variables in FlowIR

Global variables (e.g., `Global_Language`, `Global_VoiceName`, `Global_FeedbackSurveyOptIn`) are org-wide variables managed in Control Hub. To use one in a FlowIR flow, you MUST declare it in the `variables` array with its global metadata — otherwise Set Variable activities that reference it will silently fail to set the global value.

```json
{
  "name": "Global_Language",
  "description": "System-defined variable to store the language",
  "type": "STRING",
  "value": "en-US",
  "isCAD": true,
  "desktopLabel": "Customer Language",
  "isAgentEditable": false,
  "source": "GLOBAL_TM",
  "isReportable": true,
  "overwrite": false,
  "isSecure": false,
  "id": "1db241b4-21a0-4819-a258-4ebc649a8bfe",
  "isExternalized": false,
  "resourceType": ""
}
```

**How to get the global variable metadata:** Run `wxcc-flow global-vars -o json` — this returns the full object for each global variable including `id`, `source`, `isCAD`, `desktopLabel`, and `isReportable`. Copy the entire object into your FlowIR `variables` array.

**Gotcha:** A flow-local variable named `Global_Language` (without `source: "GLOBAL_TM"` and `id`) will NOT control the TTS language. The `source` and `id` fields are what link the flow variable to the org-wide global. Without them, Set Variable sets a local variable that shadows the global but doesn't affect the TTS engine.

Variable expressions use `{{double braces}}`:
- `{{NewPhoneContact.ANI}}` — start node output
- `{{varName}}` — flow variable
- `{{varName + 1}}` — arithmetic expression
- `{{ActivityName.OutputVar}}` — activity output variable

## 4. Nodes

```json
{
  "id": "node-unique-id",
  "name": "DisplayName",
  "activityType": "start|action|end|event",
  "group": "group-name",
  "properties": {
    "activityName": "activity-type-from-registry",
    ...activity-specific properties...
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | Unique within the flow. Any format works; server may normalize. |
| `name` | Yes | Display name on canvas. Also used as edge `from`/`to` reference after save. |
| `activityType` | Yes | `start` (one per flow), `action` (most activities), `end` (disconnect, end-subflow), `event` (event handlers) |
| `group` | Conditional | Required for certain activity types — see Activity Reference below |
| `properties.activityName` | Yes | Must match the registry name exactly |

### activityType Mapping

| activityType | Used By |
|-------------|---------|
| `start` | `NewContact` (start node) |
| `action` | All core and logic activities |
| `end` | `disconnect-contact`, `end-subflow`, `end` |
| `event` | Event handler triggers in `eventFlows` |

## 5. Edges

```json
{
  "id": "edge-unique-id",
  "from": "node-id-or-name",
  "to": "node-id-or-name",
  "condition": "port-condition",
  "properties": {}
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | Unique within the flow |
| `from` | Yes | Source node ID or name |
| `to` | Yes | Target node ID or name |
| `condition` | Yes | Must match an output port from the source activity — see § 7 |
| `properties` | Yes | Usually empty `{}` — server may add `{"value": "condition"}` on save |

### Default Edge Conditions

| Activity Pattern | Success Port | Error/Failure Port |
|-----------------|-------------|-------------------|
| Start node | `out` | — |
| Set Variable | `out` | `error` |
| Play Message, Play Music | `default` | `error` |
| Menu (ivr-menu) | `1`, `2`, ..., `9`, `0`, `#`, `*` | `timeout`, `invalid`, `error` |
| Condition | `true`, `false` | `error` |
| Business Hours | `workingHours`, `holidays`, `override`, `default` | `error` |
| Bridged Transfer | — (success = call bridges naturally) | `failure` |
| Blind Transfer | — (success = call transfers) | `failure` |
| Queue Contact | — (success = agent answers) | `failure` |
| Get Queue Info (queue-lookup) | `out` | `insufficientdata`, `failure` |
| Advanced Queue Info | `out` | `failure` |
| Set Contact Priority | `out` | `failure` |
| Escalate CDG | `out` | `error` |
| HTTP Request | `default` | — (no explicit error port) |
| Disconnect | — (terminal, no output ports) | — |

## 6. Event Flows

```json
{
  "eventFlows": {
    "GLOBAL_EVENTS": {
      "name": "Global Error Handling",
      "description": "...",
      "id": "GLOBAL_EVENTS",
      "onEvents": {
        "GlobalErrorHandling": "event-node-id"
      },
      "nodes": [...],
      "edges": [...]
    }
  }
}
```

Every flow should include a `GLOBAL_EVENTS` handler at minimum. The `onEvents` map links event specification names to the event node IDs that handle them. Nodes and edges inside `eventFlows` follow the same format as the main flow.

**Gotcha — node containment:** All nodes referenced by event flow edges must be declared inside the event flow's own `nodes` array. Event flow edges CANNOT reference nodes from the main flow's `nodes` array — doing so causes FC1012 ("A broken link was found at activity X in the Event Flow"). If your error handler chains to Play Message → Disconnect, both the Play Message and Disconnect nodes must be in `eventFlows.GLOBAL_EVENTS.nodes`, not in the top-level `nodes`.

Event node properties:
```json
{
  "activityName": "event",
  "eventSourceName": "WebexContactCenter",
  "eventClassificationName": "VoiceInteractions",
  "eventSpecificationName": "GlobalErrorHandling"
}
```

The server auto-resolves `eventSourceId`, `eventClassificationId`, `eventSpecificationId` from the names.

### Available Event Specifications

The API returns only 2 specs, but real flows use additional event handlers. All use `eventSourceName: "WebexContactCenter"` and `eventClassificationName: "VoiceInteractions"`.

| eventSpecificationName | Purpose |
|----------------------|---------|
| `ContactStartWorkflow` | Start node trigger (required, exactly one per flow) |
| `GlobalErrorHandling` | Unhandled error catch-all (recommended in every flow) |
| `AgentOfferContact` | Agent is offered the contact |
| `AgentContactAssigned` | Agent accepts/is assigned the contact |
| `ContactPredial` | Before outbound dial completes |
| `ContactEnded` | Contact interaction ends |
| `ContactCallbackFailed` | Scheduled callback failed |
| `ContactAniUpdated` | Caller ANI updated mid-call |
| `ContactOutboundCampaignResult` | Outbound campaign dialer result |
| `ContactReservationStarted` | Queue reservation begins |
| `FCAsk(ContactLastAgentRemoved)` | Last agent removed from contact |

## 7. Activity Reference — Tested Property Patterns

These patterns were validated by building real flows and confirming them with the `validate_flow` and `create_flow` APIs. Activities marked ✅ TESTED were used in flows that passed validation and were successfully created in a production sandbox.

### start (NewContact) — ✅ TESTED

```json
{
  "id": "node-start",
  "name": "NewPhoneContact",
  "activityType": "start",
  "properties": {
    "activityName": "start",
    "flowType": {
      "eventSourceName": "WebexContactCenter",
      "eventClassificationName": "VoiceInteractions",
      "eventSpecificationName": "ContactStartWorkflow"
    }
  }
}
```

Exactly one start node per flow. The server resolves event spec IDs from names. Output port: `out`.

### play-message — ✅ TESTED

```json
{
  "activityName": "play-message",
  "toggle": true,
  "promptsTts": [{"name": "The TTS text", "type": "tts", "value": "The TTS text"}],
  "prompts": null,
  "connector": "Cisco Cloud Text-to-Speech",
  "connector_name": "Cisco Cloud Text-to-Speech",
  "connector:name": "Cisco Cloud Text-to-Speech",
  "connector_type": "Cisco Cloud Text-to-Speech",
  "connector:type": "Cisco Cloud Text-to-Speech",
  "speakingRate": 1,
  "volumeGainDb": 0
}
```

**Gotcha:** All 5 connector fields are required — `connector`, `connector_name`, `connector:name`, `connector_type`, `connector:type`. The server needs them in multiple formats.

`toggle: true` selects TTS mode (vs. audio file). `prompts: null` disables the audio file prompt. TTS text supports `{{variable}}` references.

Output ports: `default`, `error`.

### ivr-menu (Menu) — ✅ TESTED

```json
{
  "activityName": "ivr-menu",
  "toggle": true,
  "promptsTts": [{"name": "Press 1 for Sales.", "type": "tts", "value": "Press 1 for Sales."}],
  "prompts": null,
  "connector": "Cisco Cloud Text-to-Speech",
  "connector_name": "Cisco Cloud Text-to-Speech",
  "connector:name": "Cisco Cloud Text-to-Speech",
  "connector_type": "Cisco Cloud Text-to-Speech",
  "connector:type": "Cisco Cloud Text-to-Speech",
  "menuOptions": [
    {"digit": "1", "label": "Sales"},
    {"digit": "2", "label": "Support"}
  ],
  "entryTimeout": "5",
  "speakingRate": 1,
  "volumeGainDb": 0
}
```

**Gotcha:** Use `menuOptions` for authoring, NOT `menuLinks`. The backend converts automatically. `menuLinks` is the stored format but `menuOptions` is the input format.

Group: `enum-gateway`. Output ports: `0`–`9`, `#`, `*`, `timeout`, `invalid`, `error`.

### set-variable — ✅ TESTED

```json
{
  "activityName": "set-variable",
  "activityId": "set-variable",
  "activityType": "logic",
  "setTo": "set-to-literal",
  "srcVariableType": "STRING",
  "srcVariable": "firstVarName",
  "literal": "value",
  "expr": "value",
  "setVariablesArray": [
    {
      "setTo": "set-to-literal",
      "srcVariableType": "STRING",
      "srcVariable": "firstVarName",
      "literal": "value",
      "expr": "value",
      "literal_invalid_error": false
    },
    {
      "setTo": "set-to-literal",
      "srcVariableType": "INTEGER",
      "srcVariable": "secondVarName",
      "literal": "0",
      "expr": "0",
      "literal_invalid_error": false
    }
  ]
}
```

**Gotcha:** MUST include BOTH the top-level fields (`setTo`, `srcVariableType`, `srcVariable`, `literal`, `expr`) AND the `setVariablesArray`. The top-level fields represent the first/primary variable assignment. Validation fails with FC1015 ("Required field 'Variable' is not configured") if top-level fields are missing.

Group: `set-variable`. Output ports: `out`, `error`.

For expressions: `"literal": "{{noInputCount + 1}}"`, `"expr": "{{noInputCount + 1}}"`.

### condition-activity — ✅ TESTED

```json
{
  "activityName": "condition-activity",
  "activityId": "condition-activity",
  "activityType": "logic",
  "expression": "{{noInputCount >= 3}}"
}
```

Group: `enum-gateway`. Output ports: `true`, `false`, `error`.

Expression syntax: `{{variable operator value}}`. Operators: `==`, `!=`, `>`, `<`, `>=`, `<=`. Boolean expressions evaluate to the `true` or `false` edge.

**Gotcha:** Do not reference activity output variables (like `{{TransferPharmacy.FailureCode}}`) unless you have declared a flow variable to capture that output. Validation returns FC1038 ("Variable 'X' is referenced but not declared").

### bridged-transfer — ✅ TESTED

```json
{
  "activityName": "bridged-transfer",
  "transfertodn": "1001",
  "transfertodn:radioName": "setToValue",
  "transfertodn_radioName": "setToValue",
  "timeout": 30
}
```

| Property | Required | Notes |
|----------|----------|-------|
| `transfertodn` | Yes | Dial number or `{{variable}}` reference |
| `transfertodn:radioName` | Yes | `setToValue` (literal) or `setToVariable` (variable ref) |
| `transfertodn_radioName` | Yes | Same value, alternate format |
| `timeout` | Yes | Seconds to wait for answer |
| `transferoutdigits` | No | DTMF digits to send after connect |

Output ports: `failure` only. A successful bridged transfer connects the caller and the flow has no further control — the call ends when either party hangs up. Only failure (no answer, busy, error) returns to the flow.

### blind-transfer — ✅ TESTED

```json
{
  "activityName": "blind-transfer",
  "transfertodn": "{{TransferTarget}}",
  "transfertodn:radioName": "setToVariable",
  "transfertodn_radioName": "setToVariable"
}
```

Same pattern as bridged-transfer but no `timeout` (the call is fully transferred, Flow Designer loses control). Output ports: `failure` only.

### business-hours — ✅ TESTED

```json
{
  "activityName": "business-hours",
  "businessHoursId": "<schedule-uuid-from-control-hub>"
}
```

| Property | Required | Notes |
|----------|----------|-------|
| `businessHoursId` | Yes | UUID of the schedule from Control Hub |
| `businessHoursVariable` | Yes | Variable containing schedule ID (alternative to static ID) |
| `businessHoursRadioGroup` | No | Selection mode |

Group: `enum-gateway`. Output ports: `workingHours`, `holidays`, `override`, `default`, `error`.

Use `get_choices` API with `activity_name=business-hours`, `input_name=businessHoursId` to list available schedules.

### disconnect-contact — ✅ TESTED

```json
{
  "id": "node-disconnect",
  "name": "DisconnectContact",
  "activityType": "end",
  "properties": {
    "activityName": "disconnect-contact"
  }
}
```

Terminal node — no output ports. Multiple disconnect nodes per flow are valid (one per terminal path).

### queue-contact — ✅ TESTED

**Minimal (recommended for FlowIR authoring):**

```json
{
  "activityName": "queue-contact",
  "queueId": "247ec630-c684-4a6b-8b05-7c9cfcdb8f36"
}
```

The `queueId` property is the ONLY required field. It accepts a queue UUID, a queue name, or a `{{variable}}` expression. The server auto-resolves the queue type, routing algorithm, and all internal fields. Resolve available queue values via `get_choices` with `input_name=destination` (the API input name is `destination`, but the node property the validator checks is `queueId`).

**With optional fields:**

```json
{
  "activityName": "queue-contact",
  "queueId": "247ec630-c684-4a6b-8b05-7c9cfcdb8f36",
  "fallbackQueue": "<fallback-queue-uuid>",
  "toggle": false,
  "toggleAgentAvailability": false,
  "skills": null
}
```

| Property | Required | Notes |
|----------|----------|-------|
| `queueId` | **Yes** | Queue UUID, queue name, or `{{variable}}`. This is the field the validator checks — `destination` alone will NOT pass. |
| `fallbackQueue` | No | Fallback queue UUID (recommended when using `{{variable}}` for `queueId`) |
| `toggle` | No | `true` to enable contact priority settings (default `false`) |
| `priority` | Conditional | Static priority value (int) — required when `toggle` is `true` |
| `toggleAgentAvailability` | No | `true` to check agent availability before queuing (default `false`) |
| `skills` | No | `null` for no skill routing; object for skill-based routing |

**Critical gotcha — DO NOT include `queueRadioGroup`:** The `queueRadioGroup` property (values `staticQueue` / `variableQueue`) switches the validator into "UI mode" where it expects the full `destination` + dual-format field set AND still requires `queueId`. Including it triggers cascading validation failures:
- `queueRadioGroup: "staticQueue"` requires `destination` + `destination:name` + `destination_name` + `destination:type` + `destination_type` AND `queueId` — omitting any one fails with FC1015.
- `queueRadioGroup: "variableQueue"` requires `destinationVariable` AND `skills` (even if null) AND `queueId` — omitting `skills` fails with FC1015 "Required field 'skills' is not configured".
- Omitting `queueRadioGroup` entirely lets `queueId` work as a complete shorthand with zero additional fields.

**Why `destination` alone fails:** The v2 import/validate API checks for `queueId` as the queue selection field. The `destination` property is the UI/export format — it appears in exported flows but is NOT what the validator checks on import. The activity definition API lists `destination` as the input name (and `get_choices` uses `input_name=destination`), but the actual node property the validator requires is `queueId`. This is a naming mismatch between the activity definition layer and the validation layer.

**What exported flows look like:** When a flow is created via the `queueId` shorthand (no `queueRadioGroup`), the export preserves the shorthand format — `queueId` is present and no `destination`/`queueRadioGroup` expansion occurs. This means re-importing an exported flow that was created via FlowIR works without modification. However, flows created via the Flow Designer UI export with the full property set (`destination`, `destination:name`, `destination_name`, `destination:type`, `destination_type`, `queueRadioGroup`, etc.) — re-importing those DOES require adding `queueId`.

Output ports: `failure`. Output variables: `QueueId`, `FailureCode`, `FailureDescription`.

### http-request-v2 — ✅ TESTED

**Mode 1: No connector (inline auth headers)**

```json
{
  "activityName": "http-request-v2",
  "authenticated": false,
  "httpRequestUrl": "https://api.example.com/endpoint",
  "httpRequestMethod": "GET",
  "httpRequestMethod:name": "GET",
  "httpRequestMethod_name": "GET",
  "httpContentType": "None",
  "httpContentType:name": "None",
  "httpContentType_name": "None",
  "contentType": "JSON",
  "contentType_name": "JSON",
  "httpRequestHeaders": {
    "Authorization": "Bearer {{AuthKey}}"
  },
  "outputVariableArray": [
    {
      "outputVariable": "targetVar",
      "jsonPathExp": "$.data.value"
    }
  ]
}
```

**Mode 2: With connector (managed auth)**

```json
{
  "activityName": "http-request-v2",
  "authenticated": true,
  "connectorId": "<connector-uuid>",
  "connectorId:name": "ConnectorName",
  "connectorId_name": "ConnectorName",
  "httpRequestUrl": "https://api.example.com/endpoint",
  "httpRequestMethod": "GET",
  "httpRequestMethod:name": "GET",
  "httpRequestMethod_name": "GET",
  "httpContentType": "None",
  "httpContentType:name": "None",
  "httpContentType_name": "None",
  "contentType": "JSON",
  "contentType_name": "JSON",
  "outputVariableArray": [
    {
      "outputVariable": "targetVar",
      "jsonPathExp": "$.data.value"
    }
  ]
}
```

| Property | Required | Notes |
|----------|----------|-------|
| `authenticated` | Yes | `false` = inline headers (no connector), `true` = managed connector. **Default is `true`** — omitting this requires a connector |
| `httpRequestUrl` | Yes | Full URL or `{{variable}}` |
| `httpRequestMethod` | Yes | `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`. Uses Select pattern (`:name`/`_name` suffix) |
| `httpContentType` | Yes | Request body content type. `None` for GET, `Application/JSON` for POST/PUT. Uses Select pattern |
| `contentType` | No | Response parse type (e.g. `JSON`). Uses Select pattern (`_name` suffix) |
| `httpRequestHeaders` | No | Key-value object for headers |
| `httpRequestBody` | No | Request body (for POST/PUT/PATCH) |
| `outputVariableArray` | No | Array of `{outputVariable, jsonPathExp}` mapping JSON paths to flow variables |
| `httpResponseTimeout` | No | Timeout in ms (default `2000`) |
| `retryAttempts` | No | Number of retries (default `1`) |
| `connectorId` | Conditional | Required when `authenticated` is `true`. Uses Select pattern. **Omit entirely when `authenticated` is `false`** — do not set to `null` |

**Gotcha:** The `authenticated` field defaults to `true`. If you omit it, the validator requires `connectorId`. There are TWO content-type fields: `httpContentType` (request body type) and `contentType` (response parse type). See the gotcha below about `authenticated: false` limitations.

**Gotcha — `authenticated: false` fails FlowIR validation:** Despite the activity definition showing `connectorId` as conditional on `authenticated == true`, the FlowIR validator returns FC1015 "Required field 'Connector' is not configured" when `authenticated` is `false` and no `connectorId` is provided. The "Mode 1" pattern above may work in the Flow Designer UI but does NOT work via the v2 import/validate API. **Workaround:** Always use `authenticated: true` with a connector for FlowIR-based flows. Use a Custom Connector configured in Control Hub, and include `connectorId` + `:name`/`_name` suffix fields.

Output ports: `default` (no explicit error port — use condition check after).

### fn-activity (Function) — FROM REAL FLOW

```json
{
  "activityName": "fn-activity",
  "fnVersionConfig": {
    "id": "<function-entity-id>",
    "tag": "Latest",
    "version": "2"
  },
  "fnInputVariables": [
    {"src": "ActivityName.outputVar", "target": "functionParamName", "type": "STRING"}
  ],
  "fnOutputVariables": [
    {"outputVariable": "flowVarName", "jsonPathExp": "$.returnField"}
  ]
}
```

Group: `fn-activity`. Output ports: `default`, `error`.

### ivr-collectdigits (Collect Digits) — ✅ TESTED

```json
{
  "activityName": "ivr-collectdigits",
  "toggle": true,
  "promptsTts": [{"name": "Enter your account number.", "type": "tts", "value": "Enter your account number."}],
  "prompts": null,
  "connector": "Cisco Cloud Text-to-Speech",
  "connector_name": "Cisco Cloud Text-to-Speech",
  "connector:name": "Cisco Cloud Text-to-Speech",
  "connector_type": "Cisco Cloud Text-to-Speech",
  "connector:type": "Cisco Cloud Text-to-Speech",
  "entryTimeout": "5",
  "interDigitTimeout": "3",
  "minDigits": 1,
  "maxDigits": 10,
  "terminatorSymbol": "#",
  "speakingRate": 1,
  "volumeGainDb": 0
}
```

Same connector pattern as play-message and ivr-menu. Output ports: `default` (digits collected), `timeout`, `invalid`, `error`.

### ivr-virtualassistantvoice (Virtual Agent V2) — ✅ TESTED

```json
{
  "activityName": "ivr-virtualassistantvoice",
  "connector": "NATIVE_ADVANCED_VIRTUAL_AGENT",
  "connector:name": "Webex AI Agent (Autonomous)",
  "connector_name": "Webex AI Agent (Autonomous)",
  "virtualAgentId": "<agent-id-from-choices>",
  "terminationDelay": 30,
  "speakingRate": 1,
  "volumeGain": 0,
  "pitch": 0,
  "transcript": true
}
```

**Gotcha:** `terminationDelay` is in seconds (0-30), NOT milliseconds. Default is `30`. The `connector` field uses the Select pattern (`:name`/`_name` suffix) but the VALUE is a named constant (`NATIVE_ADVANCED_VIRTUAL_AGENT` or `NATIVE_BASIC_VIRTUAL_AGENT`), NOT a UUID. Available connector values: `NATIVE_ADVANCED_VIRTUAL_AGENT` (Webex AI Agent Autonomous) and `NATIVE_BASIC_VIRTUAL_AGENT` (Webex AI Agent Scripted). The `virtualAgentId` field requires a cascading choice — you must provide the connector value as a parent parameter to get the list of available agents: `wxcc-flow choices ivr-virtualassistantvoice virtualAgentId --parent-input connector --parent-value NATIVE_ADVANCED_VIRTUAL_AGENT` (REST equivalent: `GET /{org}/project/{proj}/v2/activities/ivr-virtualassistantvoice/inputs/virtualAgentId/choices?parentInputName=connector&parentValue=NATIVE_ADVANCED_VIRTUAL_AGENT`).

Output ports: `ENDED`, `ESCALATE`, `error`.

### play-music — ✅ TESTED

```json
{
  "activityName": "play-music",
  "prompt": "<audio-file-id>",
  "audioRadioGroup": "audioFile"
}
```

No connector fields needed (unlike play-message). Output ports: `default`, `error`.

### callback — ✅ TESTED

```json
{
  "activityName": "callback",
  "callbackDn": "{{NewPhoneContact.ANI}}",
  "callbackQueue": "<queue-uuid>"
}
```

Output ports: `failure`.

### case-statement (Case) — ✅ TESTED

```json
{
  "activityName": "case-statement",
  "expression": "{{varName}}"
}
```

Group: `enum-gateway`. Output ports are dynamic — one per case value configured. Include an `error` port.

### parse-activity (Parse) — ✅ TESTED

```json
{
  "activityName": "parse-activity",
  "inputVariable": "{{HTTPRequest.responseBody}}",
  "contentType": "JSON",
  "outputVariableArray": [
    {"outputVariable": "targetVar", "jsonPathExp": "$.path.to.value"}
  ]
}
```

Group: `parse-activity`. Output ports: `default`.

**Note:** On export, `activityId` is the literal string `"parse-activity"` (not a server-generated UUID), matching the behavior of `http-request-v2`, `percent-allocation`, `wait-activity`, and `hand-off`.

### bre-request (BRE Request) — ✅ TESTED

```json
{
  "activityName": "bre-request",
  "httpQueryParameters": {"key": "{{lookupValue}}"},
  "outputVariableArray": [
    {"outputVariable": "result", "jsonPathExp": "$.attributeValue"}
  ]
}
```

Output ports: `default`.

### subflow-handoff (Subflow) — FROM REGISTRY

```json
{
  "activityName": "subflow-handoff",
  "subflowVersion": {"id": "<subflow-id>", "tag": "Latest"},
  "automaticUpdates": true,
  "subflowInputVariables": [
    {"src": "flowVar", "target": "subflowInputVar", "type": "STRING"}
  ],
  "subflowOutputVariables": [
    {"outputVariable": "flowVar", "target": "subflowOutputVar", "type": "STRING"}
  ]
}
```

Output ports: `default`, `error`.

## 7b. Additional Activity Properties

Required-property tables for activities not covered by the full snippets in § 7. Parsed from the activity definitions API (`get_activity_definitions`). The `flowDecryptAccess` toggle (boolean, optional, default `false`) appears on nearly every activity — it is omitted from the tables below for brevity.

### screen-pop (Screen Pop) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `screenPopUrl` | string | Yes | URL to display on agent desktop |
| `queryParameters` | object | No | Key-value pairs appended as query string — values can use `{{variable}}` |
| `screenPopDesktopLabel` | string | Yes | Label shown on agent desktop |
| `target` | string | Yes | `insideDesktop` or `outsideDesktop` — uses RadioGroup (direct value, no suffix fields) |

**Gotcha:** Screen-pop has an implicit `out` success port for flow continuation, despite the registry listing no output ports. The `target` field uses RadioGroup — set the value directly.

### record (Record) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `playStartTone` | boolean | Yes | Play tone before recording (default `true`) |
| `silenceTimeout` | integer | Yes | Seconds of silence before stop (default `4`) |
| `maxRecordingTime` | integer | Yes | Max recording duration in seconds (default `30`) |
| `terminationSymbol` | string | Yes | Select: `#` (default) or `*` — DTMF key to stop recording |

**Gotcha — field name confusion:** The `record` activity uses `terminationSymbol` (with Select pattern: `:name`/`_name` suffixes required). The `ivr-collectdigits` activity uses `terminatorSymbol` (plain string, no suffix fields). These are different field names on different activities — using the wrong one causes FC1015.

### RecordingControl (Recording Control) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `enableRecording` | boolean | Yes | VariableSelect — must reference a boolean flow variable (e.g. `{{enableRec}}`). Declare the variable as `BOOLEAN` type. `filterType: "boolean"`, `valueAsPebbleTemplate: true` |

### scheduled-callback (Schedule Callback) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `callbackDn` | string | No | Callback number (default `{{NewPhoneContact.ANI}}`) |
| `callbackQueue` | string | Yes | Queue UUID or variable — uses RadioGroupWithValue |
| `callbackQueue:radioName` | string | Yes | `setToValue` (static) or `setToVariable` (variable ref) |
| `callbackQueue_radioName` | string | Yes | Same value, alternate format |
| `callbackQueue:name` | string | Conditional | Queue display name (when static) |
| `callbackQueue_name` | string | Conditional | Same value, alternate format |
| `customerName` | string | No | Variable holding customer name |
| `scheduleDate` | string | Yes | Variable holding date for callback (e.g. `{{cbDate}}`) |
| `scheduleStartTime` | string | Yes | Variable holding schedule window start (e.g. `{{cbStartTime}}`) |
| `scheduleEndTime` | string | Yes | Variable holding schedule window end (e.g. `{{cbEndTime}}`) |
| `scheduleTimezone` | string | Yes | Timezone value (e.g. `America/New_York`) — uses RadioGroupWithValue |
| `scheduleTimezone:radioName` | string | Yes | `setToValue` (static) or `setToVariable` (variable ref) |
| `scheduleTimezone_radioName` | string | Yes | Same value, alternate format |

**Gotcha:** RadioGroupWithValue fields require the `:radioName` / `_radioName` suffix fields alongside the value. The `callbackQueue` and `scheduleTimezone` fields both follow this pattern.

### queue-to-agent (Queue To Agent) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `destinationVariable` | string | Yes | Variable containing agent ID or email (e.g. `{{agentEmail}}`) |
| `destinationLookupType` | string | Yes | `agentEmail` or `agentId` (from choices API) |
| `channelType` | string | Yes | `TELEPHONY`, `CHAT`, etc. (default `TELEPHONY`) |
| `queueRadioGroup` | string | No | `staticQueue` (default) |
| `reportingQueue` | string | Yes | Queue UUID for reporting — resolve via `get_choices` |
| `reportingQueue:name` | string | Yes | Queue display name |
| `reportingQueue_name` | string | Yes | Same value, alternate format |
| `destinationReportingQueueVariable` | string | Conditional | Variable alternative — required only when using variable mode |
| `priorityToggle` | boolean | No | Enable priority settings (default `false`) |
| `priorityRadioGroup` | string | Conditional | `staticPriority` or `variablePriority` — required when `priorityToggle` is `true` |
| `priority` | int | Conditional | Static priority value — required when `priorityRadioGroup` is `staticPriority` |
| `priorityVariable` | int | Conditional | Variable for priority — required when `priorityRadioGroup` is `variablePriority` |
| `parkContactToggle` | boolean | No | Park if agent unavailable (default `false`) |
| `queueRecoveryRadioGroup` | string | No | `staticRecoveryQueue` (default) |
| `recoveryQueue` | string | Yes | Recovery queue UUID — **required even when `parkContactToggle` is `false`** |
| `recoveryQueue:name` | string | Yes | Queue display name |
| `recoveryQueue_name` | string | Yes | Same value, alternate format |
| `destinationRecoveryQueueVariable` | string | Conditional | Variable alternative — required only when using variable mode |

**Gotcha:** `recoveryQueue` is always required — validation fails with FC1015 if omitted, even when `parkContactToggle` is `false`. The `priority` and `priorityVariable` fields are only required when their respective radio group mode is active.

### queue-lookup (Get Queue Info) — ✅ TESTED

```json
{
  "activityName": "queue-lookup",
  "channelType": "TELEPHONY",
  "destination": "247ec630-c684-4a6b-8b05-7c9cfcdb8f36",
  "destination:radioName": "setToValue",
  "destination_radioName": "setToValue",
  "ewtLookbackMinutes": 5
}
```

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `channelType` | string | Yes | `TELEPHONY`, `CHAT`, etc. (default `TELEPHONY`). Not exposed via `get_choices` — set directly |
| `destination` | string | Yes | RadioGroupWithValue — queue UUID or `{{variable}}`. `get_choices` returns "RadioGroupWithValue not supported" — resolve queue UUIDs via `get_choices` on `queue-contact` `destination` instead |
| `destination:radioName` | string | Yes | `setToValue` (literal UUID) or `setToVariable` (variable ref) |
| `destination_radioName` | string | Yes | Same value, alternate format |
| `ewtLookbackMinutes` | int | Yes | Lookback window in minutes for EWT calculation (range: 5–240) |

**Gotcha — no `queueId` mismatch:** Unlike `queue-contact` (where the validator requires `queueId` instead of `destination`), `queue-lookup` accepts `destination` directly with RadioGroupWithValue suffix fields. No naming mismatch.

**Gotcha — success port:** The `describe` command only lists error ports (`insufficientdata`, `failure`), but the activity has an implicit `out` success port validated via round-trip. Connect the success path using `condition: "out"`.

Output ports: `out` (success), `insufficientdata` (valid PIQ but EWT = -1), `failure` (API error or invalid queue).

Output variables: `PIQ`, `EWT`, `status`, `CallsQueuedNow`, `OldestCallTime`, `LoggedOnAgentsCurrent`, `LoggedOnAgentsAll`, `AvailableAgentsCurrent`, `AvailableAgentsAll`, `FailureCode`, `FailureDescription`.

### advanced-queue-info (Advanced Queue Info) — ✅ TESTED

```json
{
  "activityName": "advanced-queue-info",
  "channelType": "TELEPHONY",
  "queueRadioGroup": "staticQueue",
  "destination": "247ec630-c684-4a6b-8b05-7c9cfcdb8f36",
  "destination:name": "Queue-1",
  "destination_name": "Queue-1",
  "skills": {
    "skillRequirements": [],
    "relaxation": null
  }
}
```

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `channelType` | string | Yes | `TELEPHONY`, `CHAT`, etc. (default `TELEPHONY`). Not exposed via `get_choices` — set directly |
| `queueRadioGroup` | string | No | RadioGroup: `staticQueue` or `variableQueue`. Can be omitted — `destination` works without it |
| `destination` | string | Conditional | Select — queue UUID (when `staticQueue`). Resolve via `get_choices` with `input_name=destination`. Uses Select pattern (`:name`/`_name` suffix) |
| `destination:name` | string | Conditional | Queue display name |
| `destination_name` | string | Conditional | Same value, alternate format |
| `destinationVariable` | string | Conditional | VariableSelect — variable containing queue UUID (when `variableQueue`) |
| `skills` | object | **Yes** | SkillRequirementsAndRelaxation — use `{"skillRequirements": [], "relaxation": null}` for no skills. **Both `null` and `{}` fail validation with FC1015** |

**Gotcha — skills format:** The `skills` field is required and neither `null` nor `{}` passes validation. The minimum valid value is `{"skillRequirements": [], "relaxation": null}`.

**Gotcha — no `queueId` mismatch:** Unlike `queue-contact`, `advanced-queue-info` uses `destination` directly as a Select field. No naming mismatch between definition and validator.

**Gotcha — success port:** The `describe` command only lists `failure`, but the activity has an implicit `out` success port validated via round-trip.

Output ports: `out` (success), `failure`.

Output variables: `PIQ`, `LoggedOnAgentsCurrent`, `LoggedOnAgentsAll`, `AvailableAgentsCurrent`, `AvailableAgentsAll`, `CurrentGroup`, `TotalGroups`, `status`, `FailureCode`, `FailureDescription`.

### escalate-cdg (Escalate Call Distribution Group) — ✅ TESTED

```json
{
  "activityName": "escalate-cdg",
  "callDistributionGroup": "nextGroup",
  "callDistributionGroup:name": "Next Group",
  "callDistributionGroup_name": "Next Group"
}
```

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `callDistributionGroup` | string | Yes | Select: `nextGroup` (Next Group) or `lastGroup` (Last Group) — NOT a UUID. Uses Select pattern (`:name`/`_name` suffix) |
| `callDistributionGroup:name` | string | Yes | Display name: `"Next Group"` or `"Last Group"` |
| `callDistributionGroup_name` | string | Yes | Same value, alternate format |

**Gotcha — error port name:** The error port is `error` (not `failure` like most queue activities). Confirmed via `describe` and round-trip.

**Gotcha — success port:** The `describe` command only lists `error`, but the activity has an implicit `out` success port validated via round-trip.

Output ports: `out` (success), `error`.

Output variables: `CurrentGroup`, `TotalGroups`, `status`, `FailureCode`, `FailureDescription`.

### set-announcement (Set Announcement) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `toggleAgentGreeting` | boolean | No | Enable agent greeting (default `false`) |
| `attributeTag` | string | Conditional | Two feature-flag variants exist (flag `wxcc_record_agent_personal_greeting`): (1) When flag is `off`/`control` — "Attribute tag", not required. (2) When flag is `on` — "Greeting Purpose", required with defaultValue `"Default"`. Required when `toggleAgentGreeting` is `true`. Setting just `"Default"` may fail with "tag is set but version is missing" depending on greeting assets available. |
| `toggleComplianceAnnouncement` | boolean | No | Enable compliance message (default `false`) |
| `audioFile` | audioFile | Conditional | Audio file name — required when `toggleComplianceAnnouncement` is `true`. Uses Select. Use `wxcc-flow choices set-announcement audioFile` to get available files (e.g., `"defaultmusic_on_hold.wav"`) |

**Gotcha:** With both toggles off, ZERO properties beyond `activityName` are needed — the activity accepts a completely bare node. When `toggleAgentGreeting` is `true`, validation requires the `attributeTag` field — which has two feature-flag variants (see table above). The `wxcc-flow describe` command now shows both variants with `[Attribute tag]` and `[Greeting Purpose]` labels. Use `toggleComplianceAnnouncement` + `audioFile` for the simpler compliance announcement path.

### send-digits (Send Digits) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `transferoutdigits` | string | Yes | DTMF digits to send — uses RadioGroupWithValue. Static value regex: `^(?=.*[A-D0-9*#])[A-D0-9*#,]{1,32}$`. For variable reference, use `"{{varName}}"` with `setToVariable`. |
| `transferoutdigits:radioName` | string | Yes | `setToValue` (static DTMF string) or `setToVariable` (variable reference) |
| `transferoutdigits_radioName` | string | Yes | Same value as above (alternate format required by API) |

### set-contact-priority (Set Contact Priority) — ✅ TESTED

```json
{
  "activityName": "set-contact-priority",
  "priorityRadioGroup": "staticPriority",
  "priority": 1,
  "priority:name": "P1 (Priority 1)",
  "priority_name": "P1 (Priority 1)"
}
```

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `priorityRadioGroup` | string | Yes | RadioGroup: `staticPriority` or `variablePriority` — set value directly, no suffix fields |
| `priority` | int | Conditional | Select: P1=1 through P9=9 — required when `priorityRadioGroup` is `staticPriority`. Uses Select pattern (`:name`/`_name` suffix) |
| `priority:name` | string | Conditional | Display name (e.g., `"P1 (Priority 1)"`) |
| `priority_name` | string | Conditional | Same value, alternate format |
| `priorityVariable` | int | Conditional | VariableSelect — required when `priorityRadioGroup` is `variablePriority` |

**Gotcha — success port:** The `describe` command only lists `failure`, but the activity has an implicit `out` success port validated via round-trip.

Output ports: `out` (success), `failure`.

Output variables: `status`, `FailureCode`, `FailureDescription`.

### percent-allocation (Percent Allocation) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `allocations` | object[] | No | Array of allocation objects (NOT stringified JSON). Each object: `{"percent": <int>, "desc": "<label>"}`. Percentages must sum to 100. Default: `[{"percent": 100, "desc": "Allocation Default"}]` |

Output ports are dynamic — one per allocation entry (using the `desc` value as the edge condition), plus `error`. Example with 60/40 split: edges use `"condition": "PathA"` and `"condition": "PathB"` matching the `desc` values.

**Gotcha:** The `describe` output reports `allocations` as type `string[]` (array of JSON strings), but the API rejects stringified JSON — validation fails with "Percent allocation values must sum to 100 (current sum: 0.0)". Use actual objects instead. The `activityId` in exports is `"percent-allocation"` (same as activityName, not a server-generated UUID). The `group` in the FlowIR input should be `"logic"` per the `describe` output.

### wait-activity (Wait) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `duration` | string | Yes | Format `HH:MM:SS` — UI enforces min `00:00:05` / max `72:00:00`, but API accepts values outside this range. Use Duration component format |

**Gotcha:** The `activityId` field in the export comes back as `"wait-activity"` (same as activityName) instead of a UUID — `hand-off` and `percent-allocation` also exhibit this behavior.

### hand-off (GoTo) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `handOffFlow` | string | Yes | Entry point UUID — uses HandOffFlow component (fetches telephony entry points from config service). Use `wxcc-flow choices hand-off handOffFlow` to get valid entry point UUIDs. |

**Gotcha:** Validation always returns "GoTo destination is missing" (FC1015) even with valid entry point UUIDs — this is a validator limitation with the HandOffFlow component. Create succeeds regardless. The `group` in FlowIR input is `"logic"` (not `"action"` like most activities). On export, `activityId` is the literal string `"hand-off"` (not a server-generated UUID like other activities).

### generate-otp (Generate OTP) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `pinFormat` | string | Yes | `ALPHANUMERIC` (default), `NUMERIC`, or `ALPHA` — uses RadioGroup (direct value, no suffix fields) |
| `pinLength` | string | Yes | OTP length as string, valid range 4-64 (regex: `^(0*(?:[4-9]|[1-5][0-9]|6[0-4]))$`). Default `"6"` |
| `pinValidity` | string | Yes | Validity duration in seconds as string (e.g. `"300"`) |
| `pinResend` | string | Yes | RadioGroup: `GENERATE_NEW` (default) or `REUSE_SAME` |
| `transactionReference` | string | Yes | Unique transaction identifier — can use `{{variable}}` (e.g. `{{NewPhoneContact.ANI}}`) |
| `extraParameters` | object | No | Additional key-value pairs |

**Gotcha:** `pinFormat` uses RadioGroup (not RadioGroupWithValue) — set the value directly without `:radioName` suffix fields. `pinLength` and `pinValidity` are strings, not integers. The activity has an `out` success port (not documented in the `describe` output, but validated and round-tripped).

### verify-otp (Verify OTP) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `pin` | string | Yes | Variable containing the OTP to verify (e.g. `{{otpCode}}`) |
| `transactionReference` | string | Yes | Must match the generate-otp transaction reference |
| `pinFormatPrefix` | string | No | Prefix for OTP display |
| `pinFormatSuffix` | string | No | Suffix for OTP display |
| `notifyURL` | string | No | URL for notification callback |
| `resendCommand` | string | No | Command for resend behavior |
| `extraParameters` | object | No | Additional key-value pairs |

**Gotcha:** Minimal required set is just `pin` and `transactionReference`. Output ports: `error`, `failure`, `resend` — use the `resend` port to loop back to `generate-otp`.

### cryptographic-hash (Cryptographic Hash) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `algorithm` | string | No | Select: `SHA256` (default) or `SHA512` — only two options |
| `input` | string | Yes | Value to hash — can use `{{variable}}` |
| `applySalt` | boolean | No | Enable salt (default `false`) |
| `saltEncoding` | string | No | Select: `AUTO`, `TEXT` (default), `BASE64`, `HEX` |
| `salt` | string | Yes | Salt value — **always required and must be non-empty**, regardless of `applySalt` or `saltEncoding` values. The describe API reports this as conditional but validation rejects empty/missing salt in all cases |

**Gotcha:** The describe API condition (`applySalt == true && saltEncoding != AUTO`) does not match server-side validation. The `salt` field must always be present and non-empty — even when `applySalt` is `false` or `saltEncoding` is `AUTO`. Omitting it or sending `""` causes FC1015 error.

### upload-audio (Upload Audio) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `audioFileType` | string | Yes | Select: `agent_greeting` (only option — Agent Personal Greeting) |
| `greetingPurpose` | string | Yes | Up to 80 alphanumeric characters with hyphens and underscores — NO spaces allowed (FC1015 error). Use snake_case or kebab-case. |
| `audioFileData` | json | Yes | VariableSelect — must reference a JSON flow variable containing recorded audio data (use `{{varName}}` syntax) |
| `agentId` | string | Yes | VariableSelect — must reference a String flow variable containing the agent user ID (use `{{varName}}` syntax) |

**Gotcha:** `greetingPurpose` rejects spaces — use underscores or hyphens (e.g. `"Welcome_greeting"`, not `"Welcome greeting"`). Error port is `error` (not `failure`).

### start-media-stream (Start Media Stream) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `mediaDestinationId` | string | Yes | Media destination — `"Cisco AI Assistant"` (currently the only option). Value is a display name string, not a UUID. Use `wxcc-flow choices start-media-stream mediaDestinationId` to check available destinations. |

### call-progress-analysis (Call Progress Analysis) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `minSilencePeriod` | int | Yes | Min silence in ms (default `608`) |
| `analysisPeriod` | int | Yes | Analysis window in ms (default `2500`) |
| `minValidSpeech` | int | Yes | Min speech duration in ms (default `112`) |
| `maxTimeAnalysis` | int | Yes | Max analysis time in ms (default `3000`) |

**Note:** All properties are plain integers. Described as "currently supported only for callback." Output variables include `status`, `FailureCode`, and `FailureDescription`.

### LiveCallerSentiment (Live Caller Sentiment) — ⚠️ FEATURE-GATED

No configurable properties. Enable by placing the activity in the flow.

**Gotcha:** The activity definition exists in the schema catalog (`describe` and `schema` work), but creation fails with `ACTIVITY_NOT_FOUND` on orgs without the Live Caller Sentiment feature provisioned. Validation reports `valid: true` but includes a 500-level warning about the missing activity mapping.

### queue-reservation (Queue Reservation) — ⚠️ FEATURE-GATED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `toggle` | boolean | No | Enable contact priority (default `true`) |
| `priorityRadioGroup` | string | No | RadioGroup: `staticPriority` or `variablePriority` |
| `priority` | int | Conditional | Select: P1=1 through P9=9 — required when `priorityRadioGroup` is `staticPriority` |
| `priorityVariable` | int | Conditional | VariableSelect — required when `priorityRadioGroup` is `variablePriority` |

**Warning:** This activity appears in the registry metadata but returns `ACTIVITY_NOT_FOUND` on `get_choices` (HTTP 400) and `create` (HTTP 500). Validation passes with a 500-level warning. Same behavior as `flow-test-activity` and `LiveCallerSentiment` — likely feature-gated or not provisioned on all tenants. Properties above are from the registry definition and have NOT been validated via round-trip.

Output variables (from definition): `QueueId`, `status`, `FailureCode`, `FailureDescription`.

### flow-test-activity (Test Activity Flow) — ⚠️ FEATURE-GATED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `queueRadioGroup` | string | No | `staticQueue` or `variableQueue` |
| `destination` | string | Yes | Queue UUID (static mode) |
| `destinationVariable` | string | Yes | Variable for queue (variable mode) |
| `fallbackQueue` | string | Yes | Fallback queue UUID |
| `toggle` | boolean | No | Enable priority (default `false`) |
| `priorityRadioGroup` | string | No | `staticPriority` or `variablePriority` |
| `priority` | int | Yes | Static priority value |
| `priorityVariable` | int | Yes | Variable for priority |
| `toggleAgentAvailability` | boolean | No | Check agent availability (default `false`) |
| `agentAvailabilityRadioGroup` | string | No | Availability check mode |
| `agentAvailabilityVariable` | boolean | Yes | Variable for availability check |
| `skills` | object | Yes | Skill requirements and relaxation config |

**Warning:** This activity appears in the registry metadata but returns `ACTIVITY_NOT_FOUND` on both `get_choices` and `create` (HTTP 500). Validation passes with a warning. Likely feature-gated or deprecated — properties above are from the registry definition and have NOT been validated via round-trip.

### Feedback (Feedback) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `dispatch` | string | No | Survey dispatch method — `choices` endpoint returns 404 for this field |
| `language` | string | No | Survey language — uses RadioGroupWithValue |
| `customerId` | string | No | Variable with customer ID |
| `email` | string | No | Variable with customer email |
| `phoneNumber` | string | No | Variable with customer phone |

**Gotcha:** All properties are optional — a completely bare node (only `activityName`) validates and creates successfully. This is a legacy v1 activity with NO output ports at all (no error port either). Wire the exit using the `default` edge condition. The `dispatch` field's choices endpoint returns HTTP 404 — the Select values cannot be discovered programmatically.

### Feedback-V2 (Feedback V2) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `surveyMethod` | string | Yes | Survey delivery method — uses RadioGroupWithValue. Value: `inlineSurvey` for voice |
| `surveyMethod:radioName` | string | Yes | `setToValue` (static) or `setToVariable` (variable ref) |
| `surveyMethod_radioName` | string | Yes | Same value, alternate format |
| `overrideLanguageToggle` | boolean | No | Override language settings (default `false`) |
| `language` | string | Conditional | Language code — required when `overrideLanguageToggle` is `true` |
| `customerId` | string | No | Variable with customer ID (not for voice-based survey) |
| `email` | string | No | Variable with customer email (not for voice-based survey) |
| `phoneNumber` | string | No | Variable with customer phone (not for voice-based survey) |
| `customPreFills` | object | No | Key-value pre-fill data (not for voice-based survey) |
| `timeout` | int | Yes | Timeout in seconds (default `3`, not for email/SMS survey) |

**Gotcha:** `surveyMethod` uses RadioGroupWithValue — requires `:radioName` / `_radioName` suffix fields. The value `inlineSurvey` selects voice-based inline survey. `language` is only required when `overrideLanguageToggle` is `true`.

### SetCallerID (Set Caller ID) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `callerId` | string | No | Caller ID value — uses RadioGroupWithValue for static/variable. E.164 format (e.g., `"+15551234567"`) |
| `callerId:radioName` | string | No | `setToValue` (static number) or `setToVariable` (variable reference) |
| `callerId_radioName` | string | No | Same value as above (alternate format required by API) |

**Gotcha:** All properties are optional — a bare node (only `activityName`) validates and creates successfully. When `callerId` is provided, the `:radioName` / `_radioName` suffix fields are required for the value to take effect. No output ports (no error port) — wire exit using `default` edge condition.

### set-whisperannouncement (Set Whisper Announcement) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `toggle` | boolean | No | Enable TTS mode (default `false`). Set `true` for TTS |
| `prompts` | object[] | Conditional | Audio file prompts — set to `null` when using TTS mode |
| `connector` | string | Conditional | TTS connector name (same 5-field pattern as play-message) — required when `toggle` is `true` |
| `connector_name` | string | Conditional | Same value, alternate format |
| `connector:name` | string | Conditional | Same value, alternate format |
| `connector_type` | string | Conditional | Same value, alternate format |
| `connector:type` | string | Conditional | Same value, alternate format |
| `toggleLanguage` | boolean | No | Override language and voice (default `true`) |
| `voiceLanguage` | string | Conditional | Output voice selection — required when `toggleLanguage` is `true` and non-default voice desired |
| `promptsTts` | object[] | Conditional | TTS prompt objects (same format as play-message) — required when `toggle` is `true` |
| `speakingRate` | double | No | Speech rate (default `1.0`, non-Cisco connectors only) |
| `volumeGainDb` | double | No | Volume gain in dB (default `0.0`, non-Cisco connectors only) |

**Gotcha:** Uses the same 5-field connector pattern as `play-message`. When using TTS (`toggle: true`), set `prompts: null` and provide `promptsTts`. The `voiceLanguage` field is not strictly required — the server accepts the node without it and uses defaults.

### ivr-virtualassistant (Virtual Agent v1) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `connector` | string | Yes | CCAI connector UUID — resolve via `get_choices`. Uses Select pattern |
| `connector:name` | string | Yes | Connector display name |
| `connector_name` | string | Yes | Same value, alternate format |
| `interruptible` | boolean | Yes | Allow caller to interrupt prompts (default `false`) |
| `overrideLanguageToggle` | boolean | No | Override language and voice (default `true`) |
| `inputLanguage` | string | Conditional | Input language for speech recognition (e.g. `en-US`) — uses Select, 56 languages available. Required when `overrideLanguageToggle` is `true` |
| `inputLanguage:name` | string | Conditional | Same value as `inputLanguage` |
| `inputLanguage_name` | string | Conditional | Same value, alternate format |
| `outputVoice` | string | Conditional | Output voice (default `Automatic`) — uses Select, 236 voices available. Required when `overrideLanguageToggle` is `true` |
| `outputVoice:name` | string | Conditional | Same value as `outputVoice` |
| `outputVoice_name` | string | Conditional | Same value, alternate format |
| `botParameters` | object | No | Key-value pairs passed to virtual agent |
| `noInputTimeout` | int | Yes | Seconds before no-input timeout (default `5`) |
| `maxNoInputCount` | int | Yes | Max no-input retries (default `3`) |
| `dtmfTimeout` | int | Yes | DTMF inter-digit timeout (default `5`) |
| `dtmfTerminatorSymbol` | string | Yes | DTMF terminator (default `#`) |
| `terminationDelay` | int | Yes | Delay before termination in ms (default `5`) |
| `speakingRate` | double | Yes | Speech rate (default `1.0`) |
| `volumeGain` | double | Yes | Volume gain in dB (default `0.0`) |
| `transcript` | boolean | Yes | Enable conversation transcript (default `true`) |

**Gotcha:** The `connector` field uses Select pattern (UUID + `:name`/`_name` suffix), NOT the 5-field TTS connector pattern. `inputLanguage` and `outputVoice` also use Select pattern with `:name`/`_name` suffix fields. Both are only required when `overrideLanguageToggle` is `true`.

### http-request (HTTP Request v1) — ✅ TESTED

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `connectorId` | string | Yes | Custom Connector UUID — resolve via `get_choices`. Uses Select pattern |
| `connectorId:name` | string | Yes | Connector display name |
| `connectorId_name` | string | Yes | Same value, alternate format |
| `httpRequestPath` | string | No | Path appended to connector base URL (e.g. `/api/test`) |
| `httpRequestMethod` | string | Yes | `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`. Uses Select pattern |
| `httpRequestMethod:name` | string | Yes | Same value as `httpRequestMethod` |
| `httpRequestMethod_name` | string | Yes | Same value, alternate format |
| `httpQueryParameters` | object | No | Key-value query parameters |
| `httpRequestHeaders` | object | No | Key-value headers |
| `httpContentType` | string | Yes | `Application/JSON`, `TOML`, `XML`, `YAML`, `OTHER`. Uses Select pattern |
| `httpContentType:name` | string | Yes | Same value as `httpContentType` |
| `httpContentType_name` | string | Yes | Same value, alternate format |
| `httpRequestBody` | string | No | Request body (for POST/PUT/PATCH) |
| `httpResponseTimeout` | int | No | Timeout in ms (default `2000`) |
| `retryAttempts` | int | No | Number of retries (default `1`) |
| `contentType` | string | No | Response content type for parsing (e.g. `JSON`) |
| `outputVariableArray` | object[] | No | Array of `{outputVariable, jsonPathExp}` objects mapping JSON paths to flow variables |

**Key difference from http-request-v2:** v1 requires a Custom Connector (`connectorId`) and uses `httpRequestPath` relative to the connector base URL. v2 uses a full `httpRequestUrl` and does not require a connector.

**Gotcha:** `httpRequestPath` is a string (not int as originally documented). All three Select-type fields (`connectorId`, `httpRequestMethod`, `httpContentType`) require the `:name` / `_name` dual-format suffix fields. There are 7 HTTP methods available (including PATCH, HEAD, OPTIONS), not just 4.

### NewSubFlowStart (Start Subflow)

No configurable properties. Automatically placed as the entry point of a subflow. For subflow start nodes in FlowIR import, use `activityName: "start"` with `activityType: "start-subflow"` — the server resolves `start` to `NewSubFlowStart` automatically.

### end-subflow (End Subflow) (⚠️ NOT IMPORTABLE — returns ACTIVITY_NOT_FOUND on create; use `end` as substitute)

No configurable properties. Terminal node that returns control to the calling flow. Note: despite appearing in the registry and passing validation, `end-subflow` triggers `ACTIVITY_NOT_FOUND` on create. Use the `end` activity as a substitute, though it lacks the subflow return-to-caller semantics.

### end (End Flow)

No configurable properties. Terminal node for flows that need an explicit end without disconnect.

### Event (Event Handler)

No configurable input properties. Event handlers are configured via the `eventFlows` section — see § 6. The event node properties (`eventSourceName`, `eventClassificationName`, `eventSpecificationName`) are set in the node's `properties` block, not via inputGroups.

## 8. Complete Activity Registry

All activities in the Flow Designer activity registry, with their category, required `group` field, and output port conditions. The live prod registry (`GET .../v2/activities`, verified 2026-07-11) returns **52** activities: the three ⚠️ FEATURE-GATED entries below (`queue-reservation`, `LiveCallerSentiment`, `flow-test-activity`) no longer appear in it, and `ReceiveMessage` / `SendCustomMessage` (custom-messaging channel) do.

### Core Activities

| activityName | Display Name | Group | Output Ports |
|-------------|-------------|-------|-------------|
| `disconnect-contact` | Disconnect Contact | `terminating-action` | (none — terminal) |
| `play-message` | Play Message | `action` | `default`, `error` |
| `play-music` | Play Music | `action` | `default`, `error` |
| `ivr-menu` | Menu | `enum-gateway` | `0`–`9`, `#`, `*`, `timeout`, `invalid`, `error` |
| `ivr-collectdigits` | Collect Digits | `action` | `default`, `timeout`, `invalid`, `error` |
| `queue-contact` | Queue Contact | `action` | `failure` |
| `queue-to-agent` | Queue To Agent | `action` | `error` |
| `queue-lookup` | Get Queue Info | `action` | `out`, `insufficientdata`, `failure` |
| `advanced-queue-info` | Advanced Queue Info | `action` | `out`, `failure` |
| `queue-reservation` | Queue Reservation (⚠️ FEATURE-GATED) | `action` | `failure` |
| `callback` | Callback | `action` | `failure` |
| `scheduled-callback` | Schedule Callback | `action` | `failure` |
| `blind-transfer` | Blind Transfer | `action` | `failure` |
| `bridged-transfer` | Bridged Transfer | `action` | `failure` |
| `ivr-virtualassistant` | Virtual Agent | `action` | `ENDED`, `ESCALATE`, `error` |
| `ivr-virtualassistantvoice` | Virtual Agent V2 | `action` | `ENDED`, `ESCALATE`, `error` |
| `screen-pop` | Screen Pop | `action` | `out` (implicit — flow continues after pop) |
| `SetCallerID` | Set Caller ID | `action` | (none) |
| `set-announcement` | Set Announcement | `action` | `error` |
| `set-whisperannouncement` | Set Whisper Announcement | `action` | `error` |
| `set-contact-priority` | Set Contact Priority | `action` | `out`, `failure` |
| `escalate-cdg` | Escalate Call Distribution Group | `action` | `out`, `error` |
| `record` | Record | `action` | `noInputTimeout`, `undefinedErrors` |
| `RecordingControl` | Recording Control | `action` | `failure` |
| `Feedback` | Feedback | `action` | (none) |
| `Feedback-V2` | Feedback V2 | `action` | `error` |
| `start-media-stream` | Start Media Stream | `action` | `failure` |
| `send-digits` | Send Digits | `action` | `failure` |
| `call-progress-analysis` | Call Progress Analysis | `action` | `failure` |
| `LiveCallerSentiment` | Live Caller Sentiment (⚠️ FEATURE-GATED) | `action` | `failure` |
| `upload-audio` | Upload Audio | `action` | `error` |
| `cryptographic-hash` | Cryptographic Hash | `action` | `error` |
| `generate-otp` | Generate OTP | `action` | `out`, `error` |
| `verify-otp` | Verify OTP | `action` | `error`, `failure`, `resend` |
| `ReceiveMessage` | Receive Message | `action` | `timeout`, `error` |
| `SendCustomMessage` | Send Custom Message | `action` | `error` |
| `flow-test-activity` | Test Activity Flow (⚠️ FEATURE-GATED) | `action` | `failure` |

### Logic Activities

| activityName | Display Name | Group | Output Ports |
|-------------|-------------|-------|-------------|
| `set-variable` | Set Variable | `set-variable` | `out`, `error` |
| `condition-activity` | Condition | `enum-gateway` | `true`, `false`, `error` |
| `business-hours` | Business Hours | `enum-gateway` | `workingHours`, `holidays`, `override`, `default`, `error` |
| `case-statement` | Case | `enum-gateway` | (dynamic per case), `error` |
| `percent-allocation` | Percent Allocation | `logic` | (dynamic per allocation `desc`), `error` |
| `http-request` | HTTP Request (v1) | `http-request` | `default` |
| `http-request-v2` | HTTP Request (v2) | `http-request` | `default` |
| `bre-request` | BRE Request | `action` | `default` |
| `fn-activity` | Function | `fn-activity` | `default`, `error` |
| `parse-activity` | Parse | `parse-activity` | `default` |
| `hand-off` | GoTo | `logic` | `error` |
| `subflow-handoff` | Subflow | `action` | `default`, `error` |
| `wait-activity` | Wait | `action` | `error` |
| `NewContact` | Start Flow | `action` | `out` |
| `NewSubFlowStart` | Start Subflow | `action` | (none) |
| `end-subflow` | End Subflow | `terminating-action` | (none — terminal) |
| `end` | End Flow | `action` | (none) |
| `Event` | Event Handler | `action` | `out` |

## 9. Validate → Create Workflow

### Step 1: Build FlowIR

Construct the FlowIR JSON object with all nodes, edges, variables, and event flows. Save to a file.

### Step 2: Dry-Run Validate

```
POST /{orgId}/project/{projectId}/v2/flows:validate
Content-Type: application/json
Body: { FlowV2 object }
```

Response:
```json
{
  "valid": true,
  "errors": [],
  "warnings": [{"code": "FC1007", "message": "Add descriptions", "severity": "RECOMMENDATION"}],
  "summary": "FlowV2 looks valid for import/save."
}
```

Fix all ERRORs. RECOMMENDATIONs (FC1004 isolated activities, FC1007 missing descriptions) are safe to ignore.

### Step 3: Create/Import

```
POST /{orgId}/project/{projectId}/v2/flows:import?overwrite=false
Content-Type: application/json
Body: { FlowV2 object }
```

Returns `{"flow": {...}}` with the created flow metadata including `id`, `status: "Draft"`, `createdBy`, `createdDate`.

### Step 4: Verify

```
GET /{orgId}/project/{projectId}/v2/flows/{flowId}
```

Confirm the flow was created with all nodes, edges, and resolved properties.

### Step 5: Publish (Optional)

```
POST /{orgId}/project/{projectId}/flows/{flowId}:publish?skipValidation=true
```

Publishes the draft. Only available via REST API, not MCP. `skipValidation` (default `false` on the server) controls whether the server re-validates at publish time. `wxcc-flow publish` skips it by default because the CLI workflow validates explicitly beforehand (`wxcc-flow validate`) and publish-time validation can false-positive (e.g. FC1015 on hand-off flows); pass `wxcc-flow publish FLOW_ID --validate` to validate at publish time instead (both paths verified live 2026-07-11).

## 10. Common Validation Errors

| Code | Message | Fix |
|------|---------|-----|
| FC1015 | "Required field 'Variable' is not configured in Set Variable" | Add top-level `srcVariable`, `setTo`, `srcVariableType`, `literal`, `expr` to set-variable nodes |
| FC1038 | "Variable 'X' is referenced but not declared" | Declare the variable in the `variables` array, or fix the expression to reference a declared variable |
| FC1015 | "Required field 'Recovery Queue' is not configured" | Add `recoveryQueue` (UUID), `recoveryQueue:name`, `recoveryQueue_name` to `queue-to-agent` — required even when `parkContactToggle` is `false` |
| FC1015 | "One or more fields in the activity are not configured correctly" | Generic catch-all — check all required fields in the activity's §7b table. Often accompanies a more specific FC1015 |
| FC1004 | "Flow has isolated activities" | RECOMMENDATION only — nodes not reachable from start. Safe for placeholder nodes wired to Business Hours later. |
| FC1007 | "Add descriptions for activities" | RECOMMENDATION only — cosmetic |

## 11. Gotchas and Lessons Learned

### FlowIR vs Proprietary Export JSON

FlowIR is the **official API format** for programmatic flow building. It is NOT the same as the proprietary JSON from Flow Designer's UI export. Key differences:

| | FlowIR (v2 API) | Export JSON (UI) |
|-|-----------------|-----------------|
| Activity references | Names (`"activityName": "play-message"`) | UUIDs (`"activityId": "5f114466..."`) |
| Connector references | Names (`"connector": "Cisco Cloud Text-to-Speech"`) | Resolved IDs |
| Event specs | Names (`"eventSpecificationName": "GlobalErrorHandling"`) | UUIDs |
| Diagram layout | Not included (server generates) | Pixel coordinates |
| Safe to generate | **Yes** | **No** |

### Connector Field Redundancy

Play Message, Menu, Collect Digits, and Set Whisper Announcement all require 5 connector fields: `connector`, `connector_name`, `connector:name`, `connector_type`, `connector:type`. Omitting any may cause the activity to render without TTS.

### Global Variables Require Full Metadata

Global variables (like `Global_Language`) must be declared in the FlowIR `variables` array with `source: "GLOBAL_TM"` and their org-wide `id` UUID. Without these fields, a Set Variable activity that references `Global_Language` creates a local variable that shadows the global — the TTS engine and Analyzer reports won't see the change. Get the metadata via `wxcc-flow global-vars -o json` and copy the full object into `variables`. See § 3 for the complete pattern.

### Queue Creation Is Not Available via Flow APIs

The Flow Store REST API, `wxcc-flow` CLI, and MCP server can look up existing queues (`wxcc-flow choices queue-contact destination`) but cannot create new ones. Queue creation requires the WxCC Provisioning API or the Control Hub UI (`Control Hub → Contact Center → Queues → Create Queue`). Plan queue creation as a manual prerequisite before programmatic flow building.

### Set Variable Double Declaration

The `set-variable` activity requires both top-level property fields AND a `setVariablesArray`. This is the most common validation error (FC1015).

### Activity Output Variable References (FC1038)

Expressions referencing activity output variables — `{{ActivityName.OutputVar}}` (e.g., `{{CheckQueue.EWT}}`, `{{LookupAccount.httpResponseBody}}`) — trigger FC1038 "Variable 'X' is referenced but not declared" at FlowIR validation time. This applies everywhere: condition expressions, set-variable literals, parse `inputVariable`, etc.

**At runtime these references work fine** — this is purely a validation-time limitation. The validator cannot resolve activity output scopes.

**Workaround strategies by activity type:**

| Activity | Output Variable | Workaround |
|----------|----------------|------------|
| HTTP Request | `httpStatusCode`, `responseBody` | Use `outputVariableArray` to map JSON paths to declared flow variables |
| Parse | Output variables | Use `outputVariableArray` similarly |
| Queue Lookup (Get Queue Info) | `PIQ`, `EWT` | Cannot capture via `outputVariableArray` — outputs are implicit. Use static TTS text instead of `{{GetQueueInfo.PositionInQueue}}` in Play Message prompts |
| Collect Digits | `DigitsEntered` | **Avoid Collect Digits + Condition pattern entirely.** Use `ivr-menu` (Menu) instead — Menu routes directly by digit via edge conditions (`"1"`, `"2"`, etc.) without needing to reference an output variable. This is the recommended FlowIR pattern for single-digit choices. |
| Condition after any activity | `{{Activity.OutputVar}}` | Declare a flow variable, add a Set Variable node to capture the output, then reference the flow variable in the Condition. Note: the Set Variable `literal` field also triggers FC1038 if it contains `{{Activity.OutputVar}}` — this means the capture itself fails validation. The only clean workaround is to redesign the flow to avoid referencing activity outputs in expressions. |

**Design principle for FlowIR:** Prefer `ivr-menu` over `ivr-collectdigits` + `condition-activity` whenever the caller is choosing from a small set of options. Menu routes directly by digit without needing variable capture. Reserve Collect Digits for multi-digit input (account numbers, PINs) where the digits feed into a downstream HTTP Request `outputVariableArray`.

### Queue Contact `default` Edge Condition Warning

The FlowIR validator warns that `default` is not a valid condition for `queue-contact`, suggesting `failure` instead. However, `default` works correctly at runtime — the hold music/treatment path after Queue Contact executes while the caller waits for an agent. The warning is safe to ignore. Using `failure` instead would only wire the error path, not the hold treatment path. This is a validator limitation — the `queue-contact` activity's success continuation is implicit (agent answers), but the hold treatment path needs an edge condition to wire the downstream activities.

### Bridged Transfer Has No Success Path

`bridged-transfer` only has a `failure` output port. A successful transfer bridges the call and Flow Designer loses control. Design flows to only handle failure (no answer → return to menu).

### Node Names vs IDs in Edges

Both `id` and `name` work in edge `from`/`to` fields. After saving, the server normalizes to node names.

### MCP list_flows Bug

The MCP server's `list_flows` tool returns empty arrays even when flows exist. The REST API `GET /{orgId}/project/{projectId}/flows` works correctly.

### RadioGroupWithValue Pattern

Properties using `RadioGroupWithValue` (identified by the `get_choices` API returning a 400 error for that input) require suffix fields alongside the value:

```json
{
  "fieldName": "actual-value",
  "fieldName:radioName": "setToValue",
  "fieldName_radioName": "setToValue"
}
```

Use `setToValue` for static values, `setToVariable` for variable references. Activities confirmed to use this pattern: `scheduled-callback` (`callbackQueue`, `scheduleTimezone`), `Feedback-V2` (`surveyMethod`), `SetCallerID` (`callerId`), `send-digits` (`transferoutdigits`).

### RadioGroup Pattern (Direct Value, No Suffix)

Properties using `RadioGroup` (NOT `RadioGroupWithValue`) accept the value directly — no `:radioName` / `_radioName` suffix fields needed:

```json
{
  "fieldName": "NUMERIC"
}
```

Identified by the `get_choices` API returning a 400 with "is a 'RadioGroup' which does not support choices." Activities confirmed to use this pattern: `generate-otp` (`pinFormat`), `screen-pop` (`target`).

### Select Pattern (Dual-Format Name Fields)

Properties using `Select` type (identified by `get_choices` returning valid choices) require name suffix fields:

```json
{
  "fieldName": "uuid-or-value",
  "fieldName:name": "Display Name",
  "fieldName_name": "Display Name"
}
```

For entity references (queues, connectors), the value is a UUID and the name is the display name. For enum-like selects (HTTP methods, content types), the value and name are typically the same. Activities confirmed to use this pattern: `http-request` (`connectorId`, `httpRequestMethod`, `httpContentType`), `queue-contact` (`destination` for choices API, but `queueId` for the actual node property — see § queue-contact), `queue-to-agent` (`reportingQueue`, `recoveryQueue`), `ivr-virtualassistant` (`connector`, `inputLanguage`, `outputVoice`).

### Implicit Output Ports

Some activities accept edge conditions that aren't reported by the `describe` command or `get_activity_definitions` API. Known cases:
- `generate-otp`: has an `out` success port (registry only lists `error`)
- `screen-pop`: has an `out` success port (registry lists no ports)

When building flows, if an activity logically continues to the next step, try the `out` condition even if the registry doesn't list it.

### Feature-Gated Activities

Some activities appear in the registry metadata (returned by `get_activity_definitions`) but are not available for all orgs. Known cases:
- `flow-test-activity`: returns `ACTIVITY_NOT_FOUND` (HTTP 500) on both `get_choices` and `create`

Validation may pass with a warning ("Validation pipeline error") for these activities, but creation will fail. Check with `get_choices` for any required Select-type field before investing in a full flow — a 400 "Activity not found" error is the signal.

### Subflow Creation Not Supported via FlowIR Import

The `flowType: "SUBFLOW"` field in FlowIR is ignored by the import endpoint — subflows are always created as `flowType: "FLOW"`. Additionally, `end-subflow` triggers `ACTIVITY_NOT_FOUND` on create, even though it exists in the registry and passes validation. The `end` activity works as a substitute but doesn't have the subflow return-to-caller semantics.

**Consequence:** `subflow-handoff` and `fn-activity` cannot be fully round-trip tested via the CLI because they require entity IDs (subflow ID, function ID) that can't be created programmatically. These activities remain "FROM REGISTRY" / "FROM REAL FLOW" in § 7. To validate them, create the subflow/function manually in the UI, then reference the entity ID in FlowIR.

The `SubflowVersionSelect` component type used by `subflow-handoff`'s `subflowVersion` field does not support the `get_choices` API — it returns a 400 error.

### Required Fields May Not Be Truly Conditional

Some fields marked as conditional in the activity definition are actually always required by the validator. Known cases:
- `queue-to-agent`: `recoveryQueue` is always required, even when `parkContactToggle` is `false`
- `cryptographic-hash`: `salt` is always required and must be non-empty, even when `applySalt` is `false` or `saltEncoding` is `AUTO`. The activity definition marks `salt` as `required: true` with `showOnCondition: "applySalt == true && saltEncoding != AUTO"` — the `required` flag is enforced but the `showOnCondition` is ignored by the validator
- When in doubt, provide default values for all "Required: Yes" fields in the table even if the toggle appears to gate them

### Property Name Mismatches Between API Layers

Some activities have different property names in the activity definition API vs. the validation/import API. Known cases:
- `queue-contact`: The activity definition and `get_choices` API use `destination` as the input name, but the validator requires `queueId` as the node property. Using `destination` without `queueId` always fails with FC1015 "Required field 'Queue' is not configured". Use `queueId` for authoring; use `get_choices` with `input_name=destination` to resolve available queues.
- `queue-contact`: Including `queueRadioGroup` activates "UI mode" validation that requires `destination` + all dual-format fields IN ADDITION TO `queueId`. Omit `queueRadioGroup` entirely to let `queueId` work as a complete shorthand.
- `percent-allocation`: The activity definition API reports `allocations` as type `string[]` with component `PercentAllocation` and a default of `["{\"percent\":100,\"desc\":\"Allocation Default\"}"]` (an array of stringified JSON objects). The import validator rejects this format — it fails with "Percent allocation values must sum to 100 (current sum: 0.0)". The validator only accepts actual object arrays: `[{"percent":60,"desc":"PathA"},{"percent":40,"desc":"PathB"}]`. Use `object[]` semantics despite the API declaring `string[]`.
- `set-announcement`: Older definition layers returned TWO inputs named `attributeTag` — feature-flag variants distinguished by `flagName=wxcc_record_agent_personal_greeting` ("Attribute tag", not required, when `flagValue=off,control`; "Greeting Purpose", required, defaultValue="Default", when `flagValue=on`). The live prod registry (2026-07-11) resolves the flag server-side and returns ONE `attributeTag` (required, defaultValue="Default", shown when `toggleAgentGreeting == true`). When `toggleAgentGreeting` is `true`, omitting `attributeTag` fails validation.

### Cascading Choices

Some activity fields have cascading dependencies — the available choices depend on a parent field's value. Pass the parent via the CLI (verified live 2026-07-11):

```
wxcc-flow choices {activity} {input} --parent-input {parent} --parent-value {value}
```

REST equivalent:

```
GET /{org}/project/{proj}/v2/activities/{name}/inputs/{input}/choices?parentInputName={parent}&parentValue={value}
```

Known cascading fields:
- `ivr-virtualassistantvoice` → `virtualAgentId` depends on `connector` value

## 12. Property Input Type Summary

The activity definition API uses different component types for input fields. Each type has a distinct FlowIR authoring pattern. The live prod registry does not name components directly — identify them from `wxcc-flow describe <activity>` (field type, allowed values, choices endpoint) and from the `/choices` 400 message, which names the component when a field doesn't support choices (e.g., "is a 'Toggle'").

### Component Type → FlowIR Pattern

| Component | FlowIR Pattern | How to discover values |
|-----------|---------------|----------------------|
| **Select** | Value + `:name`/`_name` suffix fields. For entity refs (queues, connectors): value=UUID, name=display name. For enums (methods, content types): value and name are the same. | `wxcc-flow choices <activity> <field>` |
| **RadioGroup** | Direct value, no suffix fields. E.g., `"priorityRadioGroup": "staticPriority"` | Options visible in `wxcc-flow describe` output or try common values |
| **RadioGroupWithValue** | Value + `:radioName`/`_radioName` suffix fields. `setToValue` for static, `setToVariable` for variable ref. | `wxcc-flow describe` shows the component type; `choices` returns 400 identifying the type |
| **VariableSelect** | Flow variable reference using `{{varName}}` syntax. Declare the variable in the flow's `variables` array with the correct type. | `wxcc-flow describe` shows `filterType` (e.g., `boolean`, `string`) |
| **Toggle** | Boolean `true`/`false`. Often controls visibility of other fields via `showOnCondition`. | Check `defaultValue` in describe output |
| **Input** | Direct value (string or number). May have `validationRegex` constraints. | Check describe output for defaults and constraints |
| **CheckBox** | Boolean `true`/`false`. | Same as Toggle |
| **KeyValuePairs** | JSON object `{"key": "value"}`. Values can use `{{variable}}` syntax. | N/A |
| **OrderedList** | Array of prompt objects: `[{"name": "text", "type": "tts", "value": "text"}]` | N/A |
| **SkillRequirementsAndRelaxation** | Object: `{"skillRequirements": [...], "relaxation": null}`. Cannot be `null` or `{}`. | N/A |
| **PercentAllocation** | Array of objects: `[{"percent": 60, "desc": "PathA"}]`. API says `string[]` but validator needs `object[]`. | N/A |
| **HandOffFlow** | Entry point UUID. Validation may false-positive (FC1015) but create succeeds. | `wxcc-flow choices <activity> <field>` |
| **Duration** | String `HH:MM:SS`. Range: `00:00:05` to `72:00:00`. | N/A |
| **SubflowVersionSelect** | Object: `{"id": "<subflow-uuid>", "tag": "Latest"}`. Cannot query available subflows via choices API. | Manual: create subflow in UI, copy ID |

### Feature-Gated Activities

These activities returned `ACTIVITY_NOT_FOUND` on create when they were still listed. As of 2026-07-11 they no longer appear in the live prod registry at all.

| Activity | Status |
|----------|--------|
| `flow-test-activity` | ACTIVITY_NOT_FOUND |
| `LiveCallerSentiment` | ACTIVITY_NOT_FOUND |
| `queue-reservation` | ACTIVITY_NOT_FOUND |

### Activities with Implicit `out` Success Port

Many action-type activities have an implicit `out` success port not reported by `describe` or the activity definition API. The port works for FlowIR edge conditions. Confirmed on: `generate-otp`, `screen-pop`, `queue-lookup`, `advanced-queue-info`, `escalate-cdg`, `set-contact-priority`, `record`, `RecordingControl`, `wait-activity`, `cryptographic-hash`, `upload-audio`, `start-media-stream`, `call-progress-analysis`, `set-announcement`, `send-digits`, `SetCallerID`, `Feedback`, `percent-allocation`, `hand-off`.
