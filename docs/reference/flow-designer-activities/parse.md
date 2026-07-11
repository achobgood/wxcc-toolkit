## Parse Activity

Extracts values from structured data (JSON, XML, TOML, YAML) into flow variables using path expressions. Commonly used after HTTP Request to parse API response bodies, or after Virtual Agent V2 to extract metadata.

### Configuration

| Field | Description |
|---|---|
| Activity Label | Name for the activity |
| Activity Description | Optional description |
| Input Variable | The flow variable containing the data to parse (e.g., `{{HTTPRequest.httpResponseBody}}`, `{{VirtualAgentV2.MetaData}}`) |
| Content Type | Format of the input data: **JSON**, **XML**, **TOML**, or **YAML**. All non-JSON types are **normalized to JSON** before the path expression is evaluated. |
| Output Variable | Flow variable to receive the extracted value |
| Path Expression | **JSONPath** expression (Jayway JSONPath syntax) targeting the desired value — always JSONPath regardless of the original content type |

### Multiple Outputs

A single Parse activity can extract multiple values. Add rows to define additional Output Variable + Path Expression pairs, each targeting a different part of the same input.

### JSONPath Examples

| Path Expression | Returns |
|---|---|
| `$.status` | Top-level `status` field |
| `$.data.customer.name` | Nested field |
| `$.items[0].id` | First element of an array |
| `$.meta.resultCount` | Numeric field for conditional checks |
| `$.previous-intent.name` | Hyphenated key (common in AI agent metadata) |

### Output Variables

User-defined output variables are created per row in the configuration (one per Output Variable + Path Expression pair). In addition, the activity exposes standard error variables:

| Variable | Description |
|---|---|
| `Parse.FailureCode` | Stores the failure code. The system sets this value only when the activity fails. |
| `Parse.FailureDescription` | Stores the failure details. The system sets this value only when the activity fails. |

> **Documentation pending** — specific `FailureCode` values for Parse are not enumerated in the Cisco help docs. The values are set only on activity failure.

### Output Paths

| Output Path | Fires When |
|---|---|
| *(default exit)* | Parse completes successfully — all path expressions matched and output variables are populated |
| **Undefined Error** | System error during parsing (e.g., malformed input data, invalid path expression, content type mismatch). The flow takes this path when there are undefined system errors during flow execution. |

If no Undefined Error path is configured, the flow falls back to the `OnGlobalError` event handler in the Event Flows tab.

### Error Handling

- **Malformed input:** If the Input Variable contains data that does not match the selected Content Type (e.g., invalid JSON when Content Type is set to JSON), the activity triggers the Undefined Error path.
- **Path expression matches nothing:** When a JSONPath expression does not match any element in the input data, the target output variable receives no value. This can cause downstream activities to encounter empty/undefined variables. Use a Condition activity after Parse to check whether the output variable was populated before relying on it.

> **Documentation pending** — the exact behavior when a path expression matches nothing (whether it triggers Undefined Error or silently sets an empty value) is not explicitly documented in the Cisco help docs. Testing indicates the activity does not error; the output variable is simply empty. Verify in your environment.

### Restrictions

> **Documentation pending** — the Cisco help docs do not enumerate specific restrictions for the Parse activity. The following are inferred from documented behavior:

- Input data must match the selected Content Type; mismatches cause the Undefined Error path to fire.
- JSONPath filter expressions always return arrays, not scalars — see [http-request.md § Parse Settings](http-request.md) for the workaround.
- The activity does not support parsing binary data or file content — input must be a string variable.
- All non-JSON content types (XML, TOML, YAML) are normalized to JSON before the path expression is evaluated — the path expression is always JSONPath regardless of original format.

### Parse vs. HTTP Request Parse Settings

The HTTP Request activity has built-in Parse Settings that work identically to a standalone Parse activity. Use the standalone Parse activity when:

- You need to parse data from a non-HTTP source (Virtual Agent metadata, Global Variable JSON, Function output)
- You want to parse the same response body multiple ways in separate branches
- The data was stored in a variable earlier and needs extraction later in the flow

---

