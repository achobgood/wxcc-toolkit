# Build Flow Programmatic — Reference

Validated patterns and CLI commands for programmatic flow building via FlowIR.

## FlowIR Minimal Structure

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

## Node Template

```json
{
  "id": "unique-node-id",
  "name": "Display Name",
  "activityType": "action",
  "group": "action",
  "properties": {
    "activityName": "play-message"
  }
}
```

`activityType` and `group` vary by activity — use `wxcc-flow schema <activity>` to get the correct values.

## Validated Property Patterns

### TTS Activities (play-message, ivr-menu, ivr-collectdigits, set-whisperannouncement)

All TTS activities require the 5-field connector pattern:

```json
{
  "activityName": "play-message",
  "toggle": true,
  "promptsTts": [{"name": "prompt text", "type": "tts", "value": "prompt text"}],
  "connector": "Cisco Cloud Text-to-Speech",
  "connector_name": "Cisco Cloud Text-to-Speech",
  "connector:name": "Cisco Cloud Text-to-Speech",
  "connector_type": "Cisco Cloud Text-to-Speech",
  "connector:type": "Cisco Cloud Text-to-Speech",
  "speakingRate": 1,
  "volumeGainDb": 0
}
```

Resolve connector values via: `wxcc-flow choices play-message connector`

### Queue Contact (minimal pattern)

```json
{
  "activityName": "queue-contact",
  "queueId": "<queue-uuid>"
}
```

Do NOT include `queueRadioGroup` — it triggers "UI mode" validation. Resolve queue UUIDs via: `wxcc-flow choices queue-contact destination`

### Set Variable (double declaration)

```json
{
  "activityName": "set-variable",
  "activityId": "set-variable",
  "activityType": "logic",
  "setTo": "set-to-literal",
  "srcVariableType": "STRING",
  "srcVariable": "varName",
  "literal": "value or {{expression}}",
  "expr": "value or {{expression}}",
  "setVariablesArray": [
    {
      "setTo": "set-to-literal",
      "srcVariableType": "STRING",
      "srcVariable": "varName",
      "literal": "value or {{expression}}",
      "expr": "value or {{expression}}",
      "literal_invalid_error": false
    }
  ]
}
```

Top-level fields (`setTo`, `srcVariableType`, `srcVariable`, `literal`, `expr`) AND `setVariablesArray` are both required. Omitting either causes FC1015. For INTEGER variables, use `srcVariableType: "INTEGER"` and pass the value as a string (e.g., `"0"`).

### Condition Activity

```json
{
  "activityName": "condition-activity",
  "expression": "{{variable == value}}"
}
```

Output ports: `true`, `false`, `error`.

### Business Hours

```json
{
  "activityName": "business-hours",
  "businessHoursId": "<schedule-uuid>"
}
```

Output ports: `workingHours`, `holidays`, `override`, `default`, `error`. Resolve via: `wxcc-flow choices business-hours businessHoursId`

### HTTP Request v2

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
    {"outputVariable": "varName", "jsonPathExp": "$.path"}
  ],
  "httpResponseTimeout": 2000,
  "retryAttempts": 1
}
```

**Gotcha:** `authenticated: false` (no connector, inline headers) does NOT work via FlowIR validation — returns FC1015. Always use `authenticated: true` with a Custom Connector. Resolve connector UUIDs via `wxcc-flow choices http-request-v2 connectorId`.

### Collect Digits

```json
{
  "activityName": "ivr-collectdigits",
  "toggle": true,
  "promptsTts": [{"name": "text", "type": "tts", "value": "text"}],
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

Output ports: `default`, `timeout`, `invalid`, `error`.

### Transfers

```json
{"activityName": "bridged-transfer", "transfertodn": "{{dialNumber}}", "transfertodn:radioName": "setToVariable", "transfertodn_radioName": "setToVariable", "timeout": 10}
{"activityName": "blind-transfer", "transfertodn": "{{dialNumber}}", "transfertodn:radioName": "setToVariable", "transfertodn_radioName": "setToVariable"}
```

Both use RadioGroupWithValue for `transfertodn` — use `setToValue` for literal numbers, `setToVariable` for variable references. Bridged has `failure` port only (success = call bridges, flow loses control). Default timeout: 10 seconds. Blind has no timeout (call is fully transferred).

### Virtual Agent V2 (ivr-virtualassistantvoice)

```json
{
  "activityName": "ivr-virtualassistantvoice",
  "connector": "NATIVE_ADVANCED_VIRTUAL_AGENT",
  "connector:name": "Webex AI Agent (Autonomous)",
  "connector_name": "Webex AI Agent (Autonomous)",
  "virtualAgentId": "<agent-id>",
  "terminationDelay": 30,
  "speakingRate": 1,
  "volumeGain": 0,
  "pitch": 0,
  "transcript": true
}
```

Connector values are named constants, NOT UUIDs: `NATIVE_ADVANCED_VIRTUAL_AGENT` (Autonomous) or `NATIVE_BASIC_VIRTUAL_AGENT` (Scripted). Resolve agent IDs via cascading choices: `wxcc-flow choices ivr-virtualassistantvoice virtualAgentId --parent-input connector --parent-value NATIVE_ADVANCED_VIRTUAL_AGENT`. Output ports: `ENDED`, `ESCALATE`, `error`.

### Case Statement (case-statement)

```json
{
  "activityName": "case-statement",
  "expression": "{{varName}}"
}
```

Group: `enum-gateway`. Output ports are DYNAMIC — one per case value. Edge conditions must match case values exactly. Include `error` port.

### Percent Allocation (percent-allocation)

```json
{
  "activityName": "percent-allocation",
  "allocations": [
    {"percent": 70, "desc": "PathA"},
    {"percent": 30, "desc": "PathB"}
  ]
}
```

Group: `logic`. Allocations must be objects (NOT stringified JSON). Percentages must sum to 100. Edge conditions use the `desc` values. Include `error` port.

### Record (record)

```json
{
  "activityName": "record",
  "playStartTone": true,
  "silenceTimeout": 4,
  "maxRecordingTime": 30,
  "terminationSymbol": "#",
  "terminationSymbol:name": "#",
  "terminationSymbol_name": "#"
}
```

**Warning:** `record` uses `terminationSymbol` (Select pattern with `:name`/`_name`). `ivr-collectdigits` uses `terminatorSymbol` (plain string). Different names — using the wrong one causes FC1015.

### Scheduled Callback (scheduled-callback)

```json
{
  "activityName": "scheduled-callback",
  "callbackDn": "{{NewPhoneContact.ANI}}",
  "callbackQueue": "<queue-uuid>",
  "callbackQueue:radioName": "setToValue",
  "callbackQueue_radioName": "setToValue",
  "callbackQueue:name": "Queue-1",
  "callbackQueue_name": "Queue-1",
  "scheduleDate": "{{cbDate}}",
  "scheduleStartTime": "{{cbStartTime}}",
  "scheduleEndTime": "{{cbEndTime}}",
  "scheduleTimezone": "America/New_York",
  "scheduleTimezone:radioName": "setToValue",
  "scheduleTimezone_radioName": "setToValue"
}
```

Most complex RadioGroupWithValue activity — both `callbackQueue` and `scheduleTimezone` need `:radioName`/`_radioName` suffix fields.

### Queue To Agent (queue-to-agent)

```json
{
  "activityName": "queue-to-agent",
  "destinationVariable": "{{agentEmail}}",
  "destinationLookupType": "agentEmail",
  "channelType": "TELEPHONY",
  "reportingQueue": "<queue-uuid>",
  "reportingQueue:name": "Queue-1",
  "reportingQueue_name": "Queue-1",
  "recoveryQueue": "<queue-uuid>",
  "recoveryQueue:name": "Queue-1",
  "recoveryQueue_name": "Queue-1"
}
```

**Gotcha:** `recoveryQueue` is ALWAYS required — validation fails with FC1015 even when `parkContactToggle` is `false`.

### Advanced Queue Info (advanced-queue-info)

```json
{
  "activityName": "advanced-queue-info",
  "channelType": "TELEPHONY",
  "destination": "<queue-uuid>",
  "destination:name": "Queue-1",
  "destination_name": "Queue-1",
  "skills": {"skillRequirements": [], "relaxation": null}
}
```

**Gotcha:** `skills` is required — neither `null` nor `{}` passes. Minimum: `{"skillRequirements": [], "relaxation": null}`.

### Wait Activity (wait-activity)

```json
{
  "activityName": "wait-activity",
  "duration": "00:00:05"
}
```

Duration format: `HH:MM:SS`. Min `00:00:05`, max `72:00:00`.

### GoTo / Hand-Off (hand-off)

```json
{
  "activityName": "hand-off",
  "handOffFlow": "<entry-point-uuid>"
}
```

Group: `logic`. Resolve entry point UUIDs via `wxcc-flow choices hand-off handOffFlow`. **Note:** Validation always warns FC1015 "GoTo destination is missing" — create succeeds anyway.

## Event Flows

Minimum required: OnGlobalError. All downstream nodes (Play Message, Disconnect, etc.) must be inside the event flow's `nodes` array — they CANNOT be in the main flow's `nodes` array.

**Gotcha:** Event flow edges cannot reference main flow nodes. If your error handler wires to a Play Message and then a Disconnect, both must be declared in `eventFlows.GLOBAL_EVENTS.nodes`, not in the top-level `nodes`. Putting them in the main flow causes FC1012 ("broken link in Event Flow").

Template:

```json
"eventFlows": {
  "GLOBAL_EVENTS": {
    "name": "Global Error Handling",
    "description": "Handles unrecoverable errors",
    "id": "GLOBAL_EVENTS",
    "onEvents": {
      "GlobalErrorHandling": "node-event-error"
    },
    "nodes": [
      {"id": "node-event-error", "name": "OnGlobalError", "activityType": "event", "group": "action",
       "properties": {"activityName": "event", "eventSourceName": "WebexContactCenter",
                      "eventClassificationName": "VoiceInteractions",
                      "eventSpecificationName": "GlobalErrorHandling"}},
      {"id": "node-error-msg", "name": "ErrorMsg", "activityType": "action", "group": "action",
       "properties": {"activityName": "play-message", "toggle": true,
                      "promptsTts": [{"name": "Error message.", "type": "tts", "value": "Error message."}],
                      "prompts": null,
                      "connector": "Cisco Cloud Text-to-Speech",
                      "connector_name": "Cisco Cloud Text-to-Speech",
                      "connector:name": "Cisco Cloud Text-to-Speech",
                      "connector_type": "Cisco Cloud Text-to-Speech",
                      "connector:type": "Cisco Cloud Text-to-Speech",
                      "speakingRate": 1, "volumeGainDb": 0}},
      {"id": "node-disconnect-error", "name": "DisconnectError", "activityType": "end",
       "group": "terminating-action", "properties": {"activityName": "disconnect-contact"}}
    ],
    "edges": [
      {"id": "ev1", "from": "node-event-error", "to": "node-error-msg", "condition": "out", "properties": {}},
      {"id": "ev2", "from": "node-error-msg", "to": "node-disconnect-error", "condition": "default", "properties": {}}
    ]
  }
}
```

## Common Validation Errors

| Code | Message | Fix |
|------|---------|-----|
| FC1015 | Required field not configured | Check `wxcc-flow describe <activity>` for required fields. Common: missing Set Variable double declaration, missing connector fields |
| FC1002 | Start activity not found | Ensure one node has `activityName: "start"` with `activityType: "start"` |
| FC1004 | Isolated activities | Wire all nodes — every node must be reachable from start. This is a warning, not an error |
| FC1007 | Add descriptions for activities | Cosmetic warning — safe to ignore |
| FC0000 | Validation pipeline error | Internal validator issue — safe to ignore if no other errors |

## Key Gotchas

1. **queueId vs destination**: The choices API uses `destination` but the validator requires `queueId`. Use `wxcc-flow choices queue-contact destination` to find values, put them in `queueId`.
2. **RadioGroupWithValue suffix fields**: Fields like `callbackQueue`, `scheduleTimezone`, `surveyMethod` need `:radioName` and `_radioName` suffix fields alongside the value.
3. **Feature-gated activities**: `flow-test-activity`, `LiveCallerSentiment`, `queue-reservation` return ACTIVITY_NOT_FOUND on create despite passing validation.
4. **Subflows not importable**: `flowType: "SUBFLOW"` is ignored by the import API. `end-subflow` returns ACTIVITY_NOT_FOUND. Use `end` as substitute.
5. **fn-activity and subflow-handoff**: Require entity IDs (function ID, subflow ID) that must be created manually in the UI first.
6. **Activity output variable references (FC1038)**: `{{ActivityName.OutputVar}}` expressions fail FlowIR validation. Key design patterns to avoid FC1038:
   - **Single-digit choices:** Use `ivr-menu` (Menu) instead of `ivr-collectdigits` + `condition-activity`. Menu routes by digit via edge conditions (`"1"`, `"2"`) without referencing output variables.
   - **HTTP responses:** Use `outputVariableArray` to capture JSON paths into declared flow variables.
   - **Queue position/EWT:** Use static TTS text instead of `{{GetQueueInfo.PositionInQueue}}` — the output variable can't be captured into a flow variable via any mechanism.
   - **General rule:** Any `{{ActivityName.OutputVar}}` in a Condition expression, Set Variable literal, or TTS prompt triggers FC1038. Redesign to avoid the reference.
7. **Global variables need full metadata**: Global variables like `Global_Language` must be declared in the `variables` array with `source: "GLOBAL_TM"` and their org-wide UUID `id`. Without these, Set Variable creates a local shadow that doesn't affect TTS or Analyzer. Get the metadata via `wxcc-flow global-vars -o json`.
8. **Queue creation is outside Flow APIs**: The `wxcc-flow` CLI and MCP server can look up queues but cannot create them. Use the WxCC Provisioning API (direct curl) — see `docs/reference/wxcc-provisioning-api.md` for patterns.
9. **Queue Contact `default` edge warning**: The validator warns that `default` is not valid for `queue-contact` (suggests `failure`). Ignore this — `default` works at runtime for the hold treatment path. Using `failure` would only wire the error path.
10. **wxcli cc-* create bug**: The auto-generated `wxcli cc-team create --team-dto` (and similar) sends the JSON as a query parameter, not the request body. Use direct `curl` calls for CC resource creation. GET commands work correctly.

## CLI Command Reference

| Command | Purpose |
|---------|---------|
| `wxcc-flow template [name]` | Get a starter FlowIR template |
| `wxcc-flow schema <activity>` | Get a FlowIR node template with property hints |
| `wxcc-flow describe <activity>` | Show all input fields, types, required flags |
| `wxcc-flow choices <activity> <field>` | Resolve entity IDs (queues, connectors, schedules) |
| `wxcc-flow validate <file>` | Dry-run validate FlowIR (no save) |
| `wxcc-flow create <file>` | Import flow from FlowIR JSON |
| `wxcc-flow export <id>` | Export flow as FlowIR for verification |
| `wxcc-flow publish <id>` | Publish a draft flow |
| `wxcc-flow connectors` | List all available connectors (TTS + HTTP) |
| `wxcc-flow global-vars` | List org global variables |

## Validated Examples

Working FlowIR examples in `docs/examples/flowir/`:

| File | Pattern |
|------|---------|
| `simple-inbound.json` | Greeting → Queue → Hold Music → Disconnect |
| `menu-routing.json` | Menu → digit branches → multiple queues |
| `data-dip-routing.json` | Collect Digits → HTTP lookup → Condition branch → route |
| `business-hours-routing.json` | Business Hours → working/closed paths |
