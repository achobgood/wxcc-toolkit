## Functions Activity (Custom Code)

The Functions activity executes custom JavaScript or Python code directly within a Flow Designer flow. Use it for data transformation, routing logic, regex validation, or any computation that doesn't require caller interaction — without external API calls.

**Try Functions first.** When a voice flow needs complex data transformation (date formatting, string manipulation, JSON restructuring, routing logic), check if the Functions Activity can handle it before proposing external services, Connect webhooks, Supabase Edge Functions, or complex Pebble templates. Functions run locally in the flow with no external dependency, no latency penalty, and nothing the customer has to maintain. Only reach for external services when the logic needs network access (HTTP calls, database queries) — Functions cannot make outbound HTTP requests.

### Runtime

| Property | Value |
|----------|-------|
| Engine | Node.js 22.x |
| Languages | JavaScript, Python (3.13) |
| Code limit | ~5,000 lines |
| Max functions per org | 200 |
| Max memory per function | 128 MB |
| Execution time limit | 5 seconds |
| Max input variables | 10 |
| Output | One JSON output variable (parse individual values with JSONPath) |
| Music on wait | Automatic — prevents silence to callers during function execution. Configurable timeout 2–5 seconds (default 2 seconds). |
| Versioning | Version Labels (like flows) |

### Logging and Debugging

Console logs are not exposed from the function runtime. To capture debug information, set and access values using a custom output string array in `response.data`.

### Access Control

Supervisors and administrators can manage functions. Supervisor access is controlled by the **Function** setting (Edit, View, or None) under **Customer Experience** within the **User Profile** in Control Hub.

### Where to Create Functions

Navigate to **Control Hub > Services > Contact Center > Customer Experience > Functions**. You can also create a function from the **Functions** tab within the Flow Designer module.

### Function Signature (JavaScript)

```javascript
export const handle = async (request, response) => {
    const { variableName } = request.inputs;
    
    // Custom logic here
    
    response.data = { key: "value" };
    return response;
}
```

**Inputs:** Access flow variables mapped to the function via destructuring: `const { myVar } = request.inputs;`

**Outputs:** Assign to `response.data` as a JSON object. The calling flow extracts values using JSONPath (e.g., `$.key`).

### Configuration in Flow Designer

1. **Create the Function:** Contact Center > Flows > Functions > New Function
   - Set Name, Description, Language (JavaScript or Python)
   - Runtime auto-assigned (Node.js 22.x for JS)
2. **Define Inputs:** Click "Add Input Variable" — specify name and type (String, Integer, etc.)
3. **Write Code:** Implement the `handle` function
4. **Test:** Use the built-in test panel — provide sample input JSON, verify output under the `data` key
5. **Use in Flow:** Drag the Function activity onto the canvas
   - Select the Function and Version Label
   - Configure **Input Mappings** (flow variables → function inputs)
   - Configure **Output JSONPath** expression (e.g., `$.output`, `$.random_number`)

### Input Wiring

The Function activity canvas shows a dropdown of available flow variables to map to each function input. **Flow variables of matching type must exist before you can map them.** HTTP Request node outputs (like `httpResponseBody`) are available as selectable flow variables without creating a custom variable first.

If no flow variables of the required type exist, the Function activity shows: "No variables of type 'String' are available."

### Output Wiring

Function outputs require a **flow variable** and a **path expression**:

1. Create a flow variable in **Flow Settings > Custom Variables** (e.g., `ttsMessage`, type String)
2. On the Function activity canvas, set the **Output Variable** to the flow variable you created
3. Set the **Path Expression** to extract the value from `response.data` (e.g., `$.ttsMessage`)

| Flow Variable | Path Expression | Function Code |
|---------------|-----------------|---------------|
| `ttsMessage` | `$.ttsMessage` | `response.data = { ttsMessage: "..." }` |
| `queue_id` | `$.output.queue_id` | `response.data = { output: { queue_id: "..." } }` |

The "Output variable" field in the **Function editor** (where you write code) is **documentation only** — it describes what the function returns for other flow builders to see. The actual output mapping happens on the **Function activity** on the canvas.

### Test Panel Gotchas

The test panel input fields show a validation message: "Variable value cannot contain backslashes or double quotes. Alphanumerics, spaces and other characters are allowed." Despite this warning, **raw JSON strings work in both the test panel and at runtime.** Pasting a full JSON object (e.g., an API response body) into the test panel input field succeeds and the function processes it correctly via `JSON.parse()`. At runtime, passing `httpResponseBody` from an HTTP Request node also works.

### Importing Functions

Functions can be imported via JSON. See `docs/examples/function-import.json` for the template format. The import includes name, language, runtime, source code, input definitions, and sample output.

### Example: DNIS Data Map (Replaces Case Activities)

Instead of a multi-branch Case activity for DNIS-based routing, use a Function that returns routing data per DNIS:

```javascript
export const handle = async (request, response) => {
    const { input } = request.inputs;
    
    const dnisMap = {
        "+18005551234": {
            queue_id: "7ab606fe-0443-42db-9013-2e9e87edfeed",
            priority: 1,
            tts_message: "Thank you for calling Sales."
        },
        "+18005555678": {
            queue_id: "a1b2c3d4-5678-90ab-cdef-1234567890ab",
            priority: 2,
            tts_message: "Thank you for calling Support."
        }
    };
    
    response.data = { output: dnisMap[input] || dnisMap["default"] };
    return response;
}
```

**Input Mapping:** `input` ← `{{NewContact.DNIS}}`
**Output JSONPath:** `$.output.queue_id`, `$.output.priority`, `$.output.tts_message`

This replaces a Case activity with N branches — easier to maintain when DNIS count grows.

### Example: Random Number Generator

```javascript
export const handle = async (request, response) => {
    const { lower_bound, upper_bound } = request.inputs;
    
    if (lower_bound >= upper_bound) {
        response.data = { random_number: -1 };
        return response;
    }
    
    const result = Math.floor(Math.random() * (upper_bound - lower_bound + 1)) + lower_bound;
    response.data = { random_number: result };
    return response;
}
```

### Example: Regex Pattern Matcher

```javascript
export const handle = async (request, response) => {
    const { needle, haystack } = request.inputs;
    
    try {
        const regex = new RegExp(haystack);
        response.data = { match: regex.test(needle) };
    } catch (e) {
        response.data = { match: false };
    }
    return response;
}
```

### Output Paths

| Output Path | Fires When |
|---|---|
| **Done** | Function executed successfully and `response.data` is populated. |
| **Undefined Error** | Function threw an unhandled exception, exceeded the 5-second execution time limit, or encountered a runtime error (e.g., syntax error, memory overflow). |

> **Documentation pending** — Cisco help docs confirm that Flow Designer activities have an error handling path via the "Undefined Error" node, and that Functions supports "error messages returned by the function output, status and error codes, runtime error handling." However, the exact output path names and specific failure codes for the Functions activity are not enumerated in the Cisco help docs. The path names above ("Done" / "Undefined Error") follow the general Flow Designer error handling pattern. Verify against the canvas in your tenant.

**Error handling behavior:** If you do not connect the Undefined Error path to another activity, the flow falls back to the `OnGlobalError` event handler configured in the Event Flows tab. The Functions activity is subject to the general Flow Designer error handling rules described in "Configure error handling."

**Failure scenarios:**

| Scenario | Behavior |
|---|---|
| Unhandled exception in code | Flow takes the Undefined Error path. Error details available in flow debug logs. |
| Execution exceeds 5-second limit | Function is terminated. Flow takes the Undefined Error path. |
| Memory usage exceeds 128 MB | Function is terminated. Flow takes the Undefined Error path. |
| Code syntax error at runtime | Flow takes the Undefined Error path. |
| `response.data` not set | Function completes but output variables are empty/null. Flow takes the Done path. |

> **Self-loop limit:** The Functions activity is subject to system-enforced self-loop limits. If the activity is called in a loop that exceeds the system limit, it automatically exits via the global error path.

### Function Signature (Python)

> **Documentation pending** — Cisco help docs confirm Python 3.13 is supported but do not publish the Python handler function signature. The signature below is inferred from the JavaScript pattern and the documented input/output contract (inputs via `request.inputs`, output via `response.data`). Verify against the function editor template in your tenant.

```python
async def handle(request, response):
    variable_name = request.inputs["variableName"]

    # Custom logic here

    response.data = {"key": "value"}
    return response
```

**Inputs:** Access flow variables mapped to the function via dictionary access: `request.inputs["myVar"]`.

**Outputs:** Assign to `response.data` as a dictionary. The calling flow extracts values using JSONPath (e.g., `$.key`).

### Functions vs. Other Options

| Need | Use |
|------|-----|
| Complex data transformation, routing maps, regex | **Function** — runs locally, no external call |
| Simple string/date manipulation in Set Variable | **Pebble templates** — lighter weight |
| External API call | **HTTP Request activity** — Function cannot make network calls |
| Caller interaction (collect digits, play message) | **Standard activities** — Function is data-only |

---


