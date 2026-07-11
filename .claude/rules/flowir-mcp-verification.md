# FlowIR Properties — MCP Verification Required

When working with FlowIR activity properties — writing snippets, validating flows, or documenting property tables — you MUST get the activity definition from the MCP tools before guessing.

## Mandatory Steps

1. **Get the activity definition** via `mcp__wxcc-flow-builder__get_activity_definitions` — returns inputGroups with field names, types, required flags, defaults, and visibility conditions
2. **Check field types** via `mcp__wxcc-flow-builder__get_choices` — identifies whether a field is Select (returns choices), RadioGroup (400 error: "is a 'RadioGroup'"), or RadioGroupWithValue (400 error: "is a 'RadioGroupWithValue'")
3. **Get the node template** via `mcp__wxcc-flow-builder__get_activity_node_schema` — returns property hints and output ports
4. **Only then** write the FlowIR JSON and validate via `wxcc-flow validate`

## Hard Rules

- NEVER guess property names from exported flows — export format may differ from import format (e.g., queue-contact uses `destination` in exports but requires `queueId` for import)
- NEVER assume a field is required/optional without checking the activity definition's `required` flag and `visibleCondition`
- NEVER declare a finding based on trial-and-error without first reading the MCP definition
- NEVER assume a validation error means a field is "always required" — check whether you have other fields misconfigured first

## Known API Layer Mismatches

Property names in the activity definition API may differ from what the import validator accepts. When in doubt, test with BOTH the definition field name and the schema/template field name. Document any mismatches in `flow-designer-flowir.md` § 11 "Property Name Mismatches Between API Layers."

## If MCP Tools Are Unavailable

If the MCP server is not connected, say "I can't verify FlowIR properties without the MCP tools" and either:
- Ask the user to ensure the wxcc-flow-builder MCP server is connected
- Use `wxcc-flow describe` and `wxcc-flow choices` as a fallback (less detailed but still better than guessing)
