# FlowIR Properties — Live Verification Required (CLI-first)

When working with FlowIR activity properties — writing snippets, validating flows, or documenting property tables — you MUST get the activity definition from the live API before guessing. The `wxcc-flow` CLI is the primary tool; the `wxcc-flow-builder` MCP server is an optional alternative if the user prefers it and it is connected.

## Mandatory Steps (CLI)

1. **Get the activity definition** via `wxcc-flow describe ACTIVITY` (add `-o json` for the raw definition) — returns the flat prod shape: `inputs` (with `children`, `required`, `defaultValue`, string `showOnCondition`, `allowedValues`, `choicesEndpoint`), `outputs`, `outputPorts`, and `activityType`
2. **Resolve field values** via `wxcc-flow choices ACTIVITY INPUT` — supports `--search TERM` and cascading parents via `--parent-input PARENT --parent-value VALUE`. A 400 names the component when a field doesn't support choices (e.g. "is a 'Toggle'")
3. **Get a node template** via `wxcc-flow schema ACTIVITY` — required properties, conditional properties, import field overrides (e.g. queue-contact `destination` → `queueId`), and output ports
4. **Only then** write the FlowIR JSON and validate via `wxcc-flow validate`

If the user prefers the MCP server (`mcp__wxcc-flow-builder__*`: `get_activity_definitions`, `get_choices`, `get_activity_node_schema`), the same never-guess rules apply — but note the MCP layer returns the older `inputGroups` shape and its `list_flows` is broken; the CLI is authoritative when they disagree.

## Hard Rules

- NEVER guess property names from exported flows — export format may differ from import format (e.g., queue-contact uses `destination` in exports but requires `queueId` for import)
- NEVER assume a field is required/optional without checking the activity definition's `required` flag and `showOnCondition`
- NEVER declare a finding based on trial-and-error without first reading the live definition (`wxcc-flow describe`)
- NEVER assume a validation error means a field is "always required" — check whether you have other fields misconfigured first
- On any 500/404 from the CLI: the path moved — re-pull `GET {base}/v3/api-docs` and diff against `client.py`; do not theorize

## Known API Layer Mismatches

Property names in the activity definition API may differ from what the import validator accepts. When in doubt, test with BOTH the definition field name and the schema/template field name. Document any mismatches in `flow-designer-flowir.md` § 11 "Property Name Mismatches Between API Layers."

## If the CLI Is Unavailable

If `wxcc-flow` errors on auth (401), tell the user to regenerate the token at developer.webex.com — do not fall back to guessing. The MCP server (if connected) can serve as a backup for activity definitions and choices, subject to the same never-guess rules.
