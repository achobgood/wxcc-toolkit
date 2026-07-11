# Functions Setup

<!-- ref-tag: functions-setup-v1 -->

## When to Use Functions

**Try Functions first.** When a voice flow needs complex data transformation (date formatting, string manipulation, JSON restructuring, routing logic), check if the Functions Activity can handle it before proposing external services, Connect webhooks, Supabase Edge Functions, or complex Pebble templates. Functions run locally in the flow with no external dependency, no latency penalty, and nothing the customer has to maintain.

| Need | Use |
|------|-----|
| Complex data transformation, routing maps, regex | **Function** -- runs locally, no external call |
| Simple string/date manipulation in Set Variable | **Pebble templates** -- lighter weight |
| External API call | **HTTP Request activity** -- Function cannot make network calls |
| Caller interaction (collect digits, play message) | **Standard activities** -- Function is data-only |

**Key constraint:** Functions cannot make outbound HTTP requests. If your logic needs network access (database queries, external APIs), use an HTTP Request activity instead.

---

## Creating a Function

### Step 1: Navigate to Functions

**Control Hub > Services > Contact Center > Customer Experience > Functions**

You can also create a function from the **Functions** tab within the Flow Designer module.

### Step 2: Choose Language and Runtime

Click **New Function**, then configure:

| Setting | Options |
|---------|---------|
| **Language** | JavaScript or Python (3.13) |
| **Runtime** | Node.js 22.x (auto-assigned for JavaScript) |
| **Name** | Descriptive name (e.g., `dnis-router`, `date-formatter`) |
| **Description** | What the function does |

### Step 3: Write the Handler

#### JavaScript

```javascript
export const handle = async (request, response) => {
    const { variableName } = request.inputs;
    
    // Custom logic here
    
    response.data = { key: "value" };
    return response;
}
```

- **Inputs:** Access flow variables mapped to the function via destructuring: `const { myVar } = request.inputs;`
- **Outputs:** Assign to `response.data` as a JSON object. The calling flow extracts values using JSONPath (e.g., `$.key`).

#### Python

> **Documentation pending** -- Cisco help docs confirm Python 3.13 is supported but do not publish the Python handler function signature. The signature below is inferred from the JavaScript pattern and the documented input/output contract. Verify against the function editor template in your tenant.

```python
async def handle(request, response):
    variable_name = request.inputs["variableName"]

    # Custom logic here

    response.data = {"key": "value"}
    return response
```

- **Inputs:** Access flow variables via dictionary access: `request.inputs["myVar"]`.
- **Outputs:** Assign to `response.data` as a dictionary. The calling flow extracts values using JSONPath.

### Step 4: Define Input Variables

Click **Add Input Variable** for each input the function needs from the flow. Specify:

- **Name** -- must match the destructured variable name in code (e.g., `input`, `lower_bound`)
- **Type** -- String, Integer, etc.

Maximum 10 input variables per function.

### Step 5: Test the Function

Use the built-in test panel:

1. Provide sample input JSON for each input variable
2. Click **Test**
3. Verify the output appears under the `data` key

**Test panel gotcha:** The test panel shows a validation message: "Variable value cannot contain backslashes or double quotes. Alphanumerics, spaces and other characters are allowed." Despite this warning, **raw JSON strings work in both the test panel and at runtime.** Pasting a full JSON object (e.g., an API response body) into the test panel input field succeeds and the function processes it correctly via `JSON.parse()`.

### Step 6: Publish

Functions use **Version Labels** (like flows). Publish the function with a version label (e.g., `Dev`, `Live`) before it can be selected in a flow activity.

---

## Using a Function in a Flow

1. **Drag** the Functions activity from the activity panel onto the Flow Designer canvas
2. **Select Function:** Choose the function name from the dropdown
3. **Select Version Label:** Pick the published version (e.g., `Live`)
4. **Configure Input Mappings:** Map flow variables to function inputs. The activity shows a dropdown of available flow variables for each input. **Flow variables of matching type must exist before you can map them.** HTTP Request node outputs (like `httpResponseBody`) are available as selectable flow variables without creating a custom variable first. If no flow variables of the required type exist, the activity shows: "No variables of type 'String' are available."
5. **Configure Output:**
   - Create a flow variable in **Flow Settings > Custom Variables** (e.g., `ttsMessage`, type String)
   - On the Function activity canvas, set the **Output Variable** to the flow variable you created
   - Set the **Path Expression** to extract the value from `response.data` (e.g., `$.ttsMessage`)

**Output mapping examples:**

| Flow Variable | Path Expression | Function Code |
|---------------|-----------------|---------------|
| `ttsMessage` | `$.ttsMessage` | `response.data = { ttsMessage: "..." }` |
| `queue_id` | `$.output.queue_id` | `response.data = { output: { queue_id: "..." } }` |

**Important:** The "Output variable" field in the **Function editor** (where you write code) is **documentation only** -- it describes what the function returns for other flow builders to see. The actual output mapping happens on the **Function activity** on the canvas.

### Output Paths

| Output Path | Fires When |
|---|---|
| **Done** | Function executed successfully and `response.data` is populated. |
| **Undefined Error** | Function threw an unhandled exception, exceeded the 5-second limit, or encountered a runtime error (syntax error, memory overflow). |

If you do not connect the Undefined Error path to another activity, the flow falls back to the `OnGlobalError` event handler.

---

## Access Control

Supervisors and administrators can manage functions. Supervisor access is controlled by the **Function** setting (Edit, View, or None) under **Customer Experience** within the **User Profile** in Control Hub.

---

## Common Patterns

### DNIS Data Map (Replaces Case Activities)

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

**Input Mapping:** `input` <-- `{{NewContact.DNIS}}`
**Output JSONPath:** `$.output.queue_id`, `$.output.priority`, `$.output.tts_message`

This replaces a Case activity with N branches -- easier to maintain when DNIS count grows.

### Random Number Generator

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

### Regex Pattern Matcher

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

---

## Importing Functions

Functions can be imported via JSON. See `docs/examples/function-import.json` for the template format. The import includes name, language, runtime, source code, input definitions, and sample output.

---

## Logging and Debugging

Console logs are not exposed from the function runtime. To capture debug information, set and access values using a custom output string array in `response.data`.

---

## Limits

| Property | Value |
|----------|-------|
| Max functions per org | 200 |
| Max memory per function | 128 MB |
| Execution time limit | 5 seconds |
| Max input variables | 10 |
| Code limit | ~5,000 lines |
| Output | One JSON output variable (parse individual values with JSONPath) |
| Music on wait | Automatic -- prevents silence to callers during function execution. Configurable timeout 2-5 seconds (default 2 seconds). |

### Failure Scenarios

| Scenario | Behavior |
|---|---|
| Unhandled exception in code | Flow takes the Undefined Error path. Error details available in flow debug logs. |
| Execution exceeds 5-second limit | Function is terminated. Flow takes the Undefined Error path. |
| Memory usage exceeds 128 MB | Function is terminated. Flow takes the Undefined Error path. |
| Code syntax error at runtime | Flow takes the Undefined Error path. |
| `response.data` not set | Function completes but output variables are empty/null. Flow takes the Done path. |

The Functions activity is subject to system-enforced self-loop limits. If the activity is called in a loop that exceeds the system limit, it automatically exits via the global error path.
