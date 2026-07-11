---
name: build-flow-programmatic
description: |
  Build a WxCC Flow Designer voice flow programmatically from an existing design
  document in docs/plans/. Generates FlowIR JSON, validates via wxcc-flow CLI,
  creates the flow in the sandbox, and optionally publishes it.
  Use for: programmatic flow creation AFTER a design document exists — this is
  the programmatic alternative to build-flow-designer in the pipeline
  (design-flow → build-flow-programmatic).
  NOT for: creating the design document (use design-flow first), manual UI-based
  builds (use build-flow-designer), AI agent flows (use wxcc-agent-builder),
  Webex Connect flows (use build-action, build-digital-inbound, etc.).
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
argument-hint: [path-to-design-doc]
---

# Build Flow Programmatic Workflow

## Step 1: Load references

YOU MUST use the Read tool on each of these files sequentially. Do not proceed until all reads are complete.

1. Read `docs/reference/flow-designer-flowir.md` — §2 (FlowIR Structure), §3 (Variables), §4 (Nodes), §5 (Edges), §6 (Event Flows), §7/§7b (Activity Properties), §11 (Gotchas)
2. Read `docs/reference/flow-designer-essentials.md` — essential activity configs
3. Read this skill's `reference.md` — validated property patterns and CLI commands

**Checkpoint:** Before proceeding, confirm you can answer:
- What are the required fields in a FlowIR node? (from §4)
- What is the 5-field connector pattern for TTS activities? (from §7)
- What is the Set Variable double declaration rule? (from §11)

## Step 1.5: Check for design doc

1. If an argument was passed: read the design doc at that path
2. If no argument: use Glob to check `docs/plans/*.md` for recent flow design docs
3. If a design doc exists with Activities table (§4), Connections table (§5), Variables (§3), Event Handlers (§6): use it
4. If NO design doc exists: tell the user to run `design-flow` first. Do NOT proceed without one.

## Step 2: Parse the design doc

Extract these sections from the design doc:

| Design Doc Section | FlowIR Target |
|---|---|
| §2 Flow Metadata (name, type) | Top-level `name`, `flowType`, `description` |
| §3 Variables | `variables` array |
| §4 Activities table | `nodes` array |
| §5 Connections table | `edges` array |
| §6 Event Handlers | `eventFlows` object |
| §7 TTS Content | Activity `properties` (prompts, promptsTts) |
| §8 External Integrations | HTTP Request node properties |

## Step 2.5: Provision missing WxCC resources

Before resolving entity IDs, check whether the resources referenced in the design doc exist. The Flow Store API can only LOOK UP existing resources — it cannot CREATE teams, queues, business hours, or entry points.

1. Check existing resources: `wxcli cc-queue list`, `wxcli cc-team list`, `wxcli cc-business-hour list`, `wxcli cc-entry-point list`
2. For any resource that doesn't exist, create it via the WxCC Provisioning API. See `docs/reference/wxcc-provisioning-api.md` for the exact API patterns (required fields, gotchas).
3. Provisioning order: Site (usually exists) → Team → Queues (need team ID + CDG) → Business Hours → Entry Point (can include flowId)

**Gotcha:** `wxcli cc-* create` commands have a bug where the body is sent as a query parameter. Use direct `curl` calls for resource creation. GET commands (`list`, `show`) work correctly.

## Step 3: Resolve entity IDs

After provisioning, resolve all entity references to UUIDs:

- **Queues:** `wxcc-flow choices queue-contact destination` → get queue UUID
- **TTS Connectors:** `wxcc-flow choices play-message connector` → get connector UUID/name
- **HTTP Connectors:** `wxcc-flow choices http-request connectorId` → get connector UUID
- **Business Hours:** `wxcc-flow choices business-hours businessHoursId` → get schedule UUID
- **Entry Points (for GoTo):** `wxcc-flow choices hand-off handOffFlow` → get EP UUID
- **Global Variables:** `wxcc-flow global-vars -o json` → get the full metadata object (including `id`, `source: "GLOBAL_TM"`, `isReportable`, `isCAD`, `desktopLabel`) for any global variable referenced in the design doc (e.g., `Global_Language`, `Global_VoiceName`). Copy the entire object into the FlowIR `variables` array — without `source` and `id`, Set Variable creates a local shadow that doesn't affect the TTS engine or Analyzer.

Report the resolved IDs to the user for confirmation before proceeding.

## Step 4: Compose FlowIR JSON

Generate the complete FlowIR JSON. Follow these rules strictly:

### Node structure
Every node must have: `id`, `name`, `activityType`, `group`, `properties` (with `activityName`).

### Activity property patterns
- **TTS activities** (play-message, ivr-menu, ivr-collectdigits, set-whisperannouncement): use the 5-field connector pattern from reference.md
- **queue-contact**: use minimal `queueId` pattern — do NOT include `queueRadioGroup`
- **set-variable**: include BOTH `variable_N`/`value_N` fields AND `setVariablesArray`
- **condition-activity**: use `expression` field with `{{variable operator value}}` syntax
- **RadioGroupWithValue fields**: include `:radioName` and `_radioName` suffix fields

### Edge structure
Every edge: `id`, `from` (node id), `to` (node id), optional `condition` (port name).

### Event flows
Minimum: `OnGlobalError` with Play Message → Queue Contact → Play Music → Disconnect chain.

### Write the file
Write the FlowIR JSON to `docs/plans/flowir/{flow-name}.json`. Create the directory if needed.

## Step 5: Validate

```bash
wxcc-flow validate docs/plans/flowir/{flow-name}.json
```

- **Errors (FC1015, FC1002, etc.):** Fix the FlowIR JSON and re-validate. See reference.md for common fixes.
- **Warnings only (FC1004, FC1007):** Report to user, continue — these are recommendations, not blockers.
- **Validation pipeline errors (FC0000):** Usually ignorable — some activity validators have internal issues.

Iterate until `valid: true`.

## Step 6: Create

```bash
wxcc-flow create docs/plans/flowir/{flow-name}.json
```

Capture the flow ID from the output. If creation fails with ACTIVITY_NOT_FOUND, the activity may be feature-gated — check reference.md.

## Step 7: Verify round-trip

```bash
wxcc-flow export {flow-id} -o json
```

Spot-check that key properties survived the import: queue IDs, TTS connector names, variable assignments, edge conditions. Report any discrepancies.

## Step 8: Publish (optional)

Ask the user if they want to publish:

```bash
wxcc-flow publish {flow-id}
```

Remind them to assign the flow to an Entry Point in Control Hub (see `docs/playbooks/wxcc-setup.md`).

## Step 9: Present summary

Show:
- Flow ID and name
- Status (Draft / Published)
- Activity count and edge count
- Any validation warnings
- Next steps (assign to Entry Point, configure queues/teams if not done)

---

## CRITICAL REMINDERS

- NEVER guess FlowIR property names — always check `flow-designer-flowir.md` §7/§7b
- NEVER generate proprietary export JSON — only FlowIR
- Read the specific activity doc before composing properties for ANY activity
- The 5-field connector pattern is REQUIRED for all TTS activities
- Use `queueId` for queue-contact, NOT `destination` (see §11 Property Name Mismatches)
- Set Variable requires BOTH numbered fields AND `setVariablesArray`
- `subflow-handoff` and `fn-activity` require manually-created entity IDs — they cannot be created via the CLI
- `end-subflow` is NOT importable — use `end` as a substitute
- Always validate before creating — `wxcc-flow validate` catches most errors before they hit the server
