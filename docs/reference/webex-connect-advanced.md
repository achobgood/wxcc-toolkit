# Webex Connect — Advanced Node Reference

<!-- ref-tag: connect-advanced-v1 -->

Advanced node types for AI agent action flows. Load this reference when the action requires error routing, data transformation, or side-effect notifications (SMS, email, RCS, Apple Messages, WhatsApp). All nodes documented here are safe within the 30-second agent flow timeout.

**Prerequisite:** This document assumes familiarity with `webex-connect.md`. Read that first for core concepts (Receive node, HTTP nodes, Variable Picker, Flow Outcomes).

---

## Branch Node (Conditional Logic)

Routes flow execution based on if/then/else conditions. Evaluates conditions top-to-bottom; first match wins. If nothing matches, the default "None of the above" outcome fires.

### When to Use in AI Agent Flows

Check an HTTP status code before returning data to the agent. Example: if a patient lookup returns 404, route to a Flow Outcomes node that tells the agent "no record found" instead of returning empty data.

### Configuration

- **Input Variable**: e.g., `$(n3.https.statusCode)`
- **Condition operators**: Equals, Not equals, Contains, Starts with, Ends with, Regex, Less than, Greater than, Between, In/Not in, Contains ignore case, Equals ignore case
- **Logical operators**: AND / OR to combine multiple conditions per branch
- **Outcomes**: one exit edge per branch + "None of the above" default + onError

### Example: HTTP Error Routing

```
HTTP Request (Node 3)
  → Branch (Node 4): $(n3.https.statusCode) equals "200"
    → [Yes] → Flow Outcomes (return data)
    → [None of the above] → Flow Outcomes (return error message)
```

**Key detail**: HTTP 4xx responses go through the HTTP node's **onSuccess** edge (the request completed), not onError. You must branch on `statusCode` to handle them.

---

## Evaluate Node (JavaScript Execution)

Executes inline JavaScript within a flow. The most powerful data manipulation node — handles string operations, date math, conditional logic, array manipulation. Runs on **Mozilla Rhino** (Java-based JS engine). `let`/`const` work for local declarations; arrow functions and template literals do **not**. Error messages and type representations (e.g., `org.mozilla.javascript.NativeArray` for arrays) reflect Rhino, not V8.

### When to Use in AI Agent Flows

- **Date/time conversion**: Convert UTC timestamps to local time in the flow instead of relying on the LLM (which does this unreliably)
- **String formatting**: Concatenate or reformat values between HTTP nodes
- **Derived values**: Compute values that don't come directly from an API response

### How the Evaluate Node Actually Works

The Evaluate node returns **one result** — the value of the last evaluated expression in the script. It does NOT produce multiple named output variables from `var` declarations.

| Concept | What It Does |
|---------|-------------|
| **Configure Script Output** | Names the single result. It appears in the Output Variables panel as `$(nX.outputName)` and is primarily used for branch routing (e.g., `continue`, `failed`, `valid`) |
| **Branch Name** | Creates a routing path that matches the result string — wire each branch to downstream nodes |
| **Custom flow variables** | How you pass **multiple data values** to downstream nodes. Create them in Flow Settings > Custom Variables, then assign them inside the script (without `var`). Referenced as `$(variableName)` — no node prefix |
| **`+ Add New` button** | Adds another **script block** with its own script, output name, and branch — NOT an "additional output" on the same script |

### Variable Reference Formats

| Source | Format | Example |
|--------|--------|---------|
| Custom flow variables (set in Evaluate script) | `$(variableName)` — no node prefix | `$(oncall_number)`, `$(retryCount)` |
| Script output (last expression) | `$(nX.outputName)` — also matched against Branch Name for routing | `$(n5.continue)` — value is the routing string |
| HTTP Request outputs | `$(nX.https.property)` for built-ins, `$(nX.variableName)` for parsed outputs | `$(n3.https.statusCode)`, `$(n3.oncall_csv)` |

To pass multiple data values from an Evaluate node to downstream nodes, use **custom flow variables** — create them in Flow Settings > Custom Variables, assign them inside the script (without `var`), and reference them as `$(variableName)` with no node prefix. The script output (named via "Configure Script Output") is a single value primarily used for **branch routing**.

**Official docs vs. observed behavior:** The docs state "The Evaluate node script returns the result as a decimal value." In practice, string returns (`"continue"`, `"failed"`) work for branch routing — confirmed by live testing. Writing to custom flow variables from within the script (by assigning without `var`) is observed behavior, not explicitly documented.

### Configuration

- **Script input**: JavaScript code block (Rhino engine — `let`/`const` supported, no arrow functions or template literals)
- **Configure Script Output**: names the single result — appears in Output Variables panel and used for branch routing
- **Branch Name**: routing path that matches the result — wire to downstream nodes
- **Variable access**: use `$(variableName)` syntax inside the script to read flow variables — case-sensitive

### Custom Variable Prerequisite

Per the official docs: a custom variable must be **referenced in one or more preceding nodes** in the flow (in the Configuration tab or Transition Actions tab) for its value to populate during flow execution. If the Evaluate script reads a custom variable that hasn't been referenced upstream, it may arrive empty.

### Testing the Script

The Evaluate node has a test panel (right side of the script editor) with **Variable Name / Value** fields. Add entries for each `$(variableName)` your script references so you can run the script in isolation before deploying.

### Built-in Libraries (include via `includeJs(libraryName)`)

| Library | Functions |
|---------|-----------|
| `imi_general` | typeof, length, URL encode/decode |
| `imi_base64` | base64 encode/decode |
| `imi_strings` | indexOf, replace, slice, substring |
| `imi_array` | concat, indexOf, isArray, join, push, reverse, splice |

### Gotchas and Constraints

**Exit paths:** Every Evaluate node has three automatic outcomes:
1. Named success branches (matching the script's output value)
2. `onInvalidChoice` — code executes successfully but output matches no configured branch name
3. `onError` — code execution fails (syntax error, runtime exception)

Wire `onInvalidChoice` to a fallback path to avoid silent flow failures when the script returns an unexpected value.

**Two success branches cannot connect to the same downstream node.** If you need branches `a` and `b` to both reach the same next node, use a "passthrough" Evaluate between them, or restructure to use a single branch name.

**Node output variables are read-only inside Evaluate.** Modifying a variable that came from a previous node's output (like `$(n3.statusCode)`) inside the script does NOT change its value downstream. Only custom flow variables (assigned without `var`/`let`/`const`) persist changes to flow scope.

**Variable shadowing causes errors.** If a flow already has a variable named `email` (from a webhook input or previous node), writing `let email = email;` or `const email = $(n2.email);` causes a scope clash. Use a different local name:
```javascript
const userEmail = "$(n2.email)";
```

**On-Leave workaround for scoping:** If you need a node's output variable available in an Evaluate but hit scoping issues, use the preceding node's **Transition Actions > On-Leave > Set Variable** to copy the value into a custom flow variable before the Evaluate node executes.

**Library invocation pattern:** Import with lowercase, reference with UPPERCASE:
```javascript
includeJs("imi_strings");
var idx = IMI_STRINGS.indexOf("hello world", "world");
```

### Example: Loop with retryCount (Sequential Dialing Pattern)

This pattern uses custom flow variables (`oncall_number`, `retryCount`, `maxRetryCount`) to loop through a list of phone numbers. One Evaluate + one Call Patch replace the old 3-Call-Patch chain.

**Custom flow variables (create in Flow Settings > Custom Variables):**
- `retryCount` — init `0`
- `maxRetryCount` — init `2`
- `oncall_number` — init empty

**Script:**
```javascript
var csv = "$(n4.oncall_csv)";
var numbers = csv.split(",");

if (Number(retryCount) <= Number(maxRetryCount)) {
    if (Number(retryCount) === 0) {
        oncall_number = numbers[0] ? numbers[0].trim() : "";
    }
    if (Number(retryCount) === 1) {
        oncall_number = numbers[1] ? numbers[1].trim() : "";
    }
    if (Number(retryCount) === 2) {
        oncall_number = numbers[2] ? numbers[2].trim() : "";
    }
    retryCount = Number(retryCount) + 1;
    "continue";
} else {
    "failed";
}
```

**Configure Script Output:** `continue`
**Branch Names:** `continue` (wire to Call Patch), `failed` (wire to fallback TTS)

**Test evidence (from live flow execution):**
```json
{
  "_wfnoderesult": "continue",
  "oncall_number": "9103915567",
  "retryCount": "1.0",
  "_wferrorstatus": "3003",
  "_wferrordesc": "result : continue"
}
```

- `_wfnoderesult` = the script output (last expression) — used for branch routing
- `oncall_number` = custom flow variable set by the script — referenced downstream as `$(oncall_number)`
- `retryCount` = custom flow variable incremented by the script
- `3003` = informational status, not an error

### Example: UTC to Eastern Time Conversion

```javascript
var utcTime = new Date("$(n3.scheduled_at)");
var jan = new Date(utcTime.getFullYear(), 0, 1);
var jul = new Date(utcTime.getFullYear(), 6, 1);
var stdOffset = Math.max(jan.getTimezoneOffset(), jul.getTimezoneOffset());
var isDST = utcTime.getTimezoneOffset() < stdOffset;
var offset = isDST ? 4 : 5;
utcTime.setHours(utcTime.getHours() - offset);
var etTime = utcTime.toISOString();
```

**Note:** This JavaScript runs on the Connect server (not in the caller's browser), so `getTimezoneOffset()` reflects the server's timezone. If the server is UTC, use a simpler approach — hardcode the offset but document which months require -4 vs -5:

```javascript
var month = new Date("$(n3.scheduled_at)").getUTCMonth();
var offset = (month >= 2 && month <= 10) ? 4 : 5;
var utcTime = new Date("$(n3.scheduled_at)");
utcTime.setHours(utcTime.getHours() - offset);
var etTime = utcTime.toISOString();
```

This replaces the unreliable "tell the LLM to subtract 5 hours" pattern with a deterministic conversion. For precise DST boundaries, use an RPC function in the database instead.

---

## Error Handling on HTTP Request Nodes

### Exit Paths

Every HTTP Request node has three exit edges:

| Edge | Trigger | Visual |
|------|---------|--------|
| **onSuccess** | HTTP request completed (ANY status code, including 4xx/5xx) | Green |
| **onError** | Connection failure, invalid input, internal error | Red |
| **onTimeout** | No response within configured timeout | Orange |

### Critical: 4xx/5xx Goes Through onSuccess

A `404 Not Found` or `500 Server Error` exits via **onSuccess**, not onError. The request completed — it just returned an error status. To handle HTTP errors, wire a **Branch node** after the HTTP node and check `$(nX.https.statusCode)`.

### Timeout Configuration

- **Connection Timeout**: max 20,000ms
- **Request Timeout**: max 20,000ms

Keep both well under 20s to leave headroom within the 30-second agent flow timeout.

### Recommended Error Pattern for Agent Flows

```
HTTP Request → Branch (statusCode == 200?)
  → [Yes] → Flow Outcomes (return data)
  → [No]  → Flow Outcomes (return error_message: "Could not find record")
```

Do NOT use retry loops — they'll exceed the 30-second timeout. Fail fast and let the agent handle it conversationally.

---

## Transition Actions (Set Variable / Debug Logging)

Every node has a **Transition Actions** tab with On-enter and On-leave events. These let you capture or log values without adding a standalone node.

### Set Variable

Capture a node output into a custom flow variable. Useful for renaming or storing intermediate values.

- Max 30 variables per Set Variable operation
- Variables are case-sensitive

### Debug Logging

| Action | Purpose | Requirement |
|--------|---------|-------------|
| **Log all Flow Variables** | Snapshot all variables to transaction log | "Descriptive logging" enabled in Flow Settings |
| **Log a Value** | Log specific variable with a Log ID (integer > 1000) | Same |

### When to Use in AI Agent Flows

- Capture an HTTP response field into a named variable for use in a later Branch condition
- Debug a flow that's returning unexpected data — enable descriptive logging temporarily, then check transaction logs

---

## Data Parser Node

Extracts fields from JSON or XML data using JSONPath. A standalone version of the HTTP Request node's built-in output variable parsing.

### When to Use

Only when the HTTP node's built-in Parse button can't handle the response structure — e.g., deeply nested JSON, or re-parsing data already stored in a variable.

### Configuration

1. **Import Data From**: variable containing JSON (e.g., `$(n4.https.responseBody)`)
2. **Input Data Format**: JSON or XML
3. **Sample Body**: paste representative response, click **Parse**
4. Select fields to extract, each gets a JSONPath (e.g., `$.data.nested.field`) and output variable name

For typical REST API responses, the HTTP node's built-in parsing is sufficient. Reach for this node only when it isn't.

---

## Variable Scoping

### Flow-level Custom Variables

- Created in **Flow Settings > Custom Variables** tab or inline on any node
- Available throughout the entire flow
- Can be "externalized" to defer value assignment until flow launch

### No Org-level Secrets Manager

Webex Connect does NOT have a built-in org-level variable store or secrets manager. Options for API keys:

| Approach | Trade-off |
|----------|-----------|
| Hardcode in each flow | Simple but duplicated; fine for demo |
| Externalized variables | Set per flow at launch; better for multi-env |
| Node Runtime Authorization | OAuth/API key configs stored at service level, selectable in HTTP node |

---

## SMS Node (Side-Effect Notifications)

Sends an SMS message to a customer via the configured SMS gateway. In AI agent flows, use it as a **side effect** — fire-and-forget confirmation after the core API work is done, before returning data through Flow Outcomes.

### When to Use in AI Agent Flows

After an HTTP POST creates a record (appointment, order, etc.), drop an SMS node between the last HTTP node and Flow Outcomes to send a confirmation text. The agent still returns structured data to the caller; the SMS is a bonus notification.

```
Receive → HTTP GET (lookup) → HTTP POST (create) → SMS → Flow Outcomes → End
```

### Required Configuration

| Field | Value | Notes |
|-------|-------|-------|
| **Destination Type** | `msisdn` | Mobile number in international format |
| **Destination** | Variable from flow (e.g., `$(n2.aiAgent.phone_number)`) | Must include country code; use variable picker |
| **From Number** | Select from dropdown | Pre-configured sender ID in your Connect tenant |
| **Message Type** | `Text` | Plain text; max 1024 characters |
| **Message** | Body text with variables | Use `\n` for line breaks; insert variables via picker |

### Critical: Wait For Setting

The SMS node has two execution modes under **Advanced Options**:

| Mode | Behavior | Use in agent flows? |
|------|----------|---------------------|
| **Gateway Submit** | Node completes as soon as the message enters the gateway queue | **Yes** — fast, stays under 30s |
| **Delivery Report** | Node waits for carrier delivery confirmation | **No** — can take seconds to minutes, will timeout |

**Always set Wait For to "Gateway Submit"** in AI agent flows. Delivery Report mode blocks the flow waiting for carrier confirmation, which regularly exceeds the 30-second agent timeout.

### Example: Appointment Confirmation SMS

After `create_appointment` returns a confirmation number, send a text before Flow Outcomes:

**Message body:**
```
Your booking is confirmed.\nConfirmation: $(n5.confirmation_number)\nDate: $(n5.scheduled_at)\nPlease arrive 15 minutes early.
```

- `n5` references the HTTP POST node that created the appointment — adjust node number via variable picker
- The SMS fires on the HTTP node's **onSuccess** edge, same path as Flow Outcomes
- If SMS fails, wire its **onError** edge directly to Flow Outcomes so the agent still gets the appointment data

### Exit Edges

| Edge | Trigger |
|------|---------|
| **onSuccess** | Message accepted by gateway (Gateway Submit mode) |
| **onError** | Invalid destination, misconfigured sender, gateway rejection |
| **onTimeout** | Expiry threshold exceeded (only relevant in Delivery Report mode) |

---

## Email Node (Side-Effect Notifications)

Sends an email to a recipient via the configured email asset. In AI agent flows, use it as a **side effect** — fire-and-forget confirmation after the core API work is done, before returning data through Flow Outcomes.

### When to Use in AI Agent Flows

After an HTTP POST creates a record (appointment, order, etc.), drop an Email node between the last HTTP node and Flow Outcomes to send a confirmation email with details the patient can reference later (confirmation number, prep instructions, location info).

```
Receive → HTTP GET (lookup) → HTTP POST (create) → Email → Flow Outcomes → End
```

### Required Configuration

| Field | Value | Notes |
|-------|-------|-------|
| **Destination Type** | `Email ID` | Use Email ID for direct address targeting |
| **Destination ID** | Variable from flow (e.g., `$(n3.patient_email)`) | Supports multiple comma-separated addresses; use variable picker |
| **From Email** | *(auto-populated)* | Pulled from the email app asset config; field is disabled on the node |
| **From Name** | Display name (e.g., `Acme Services`) | Optional but recommended for professional appearance |
| **Subject** | Subject line with variables | e.g., `Appointment Confirmed - $(n5.confirmation_number)` |
| **Email Type** | `Text` or `HTML` | Text for simple confirmations; HTML for branded templates |
| **Message** | Body content with variables | Insert variables via picker; use HTML markup if Email Type is HTML |

### Optional Fields

| Field | Notes |
|-------|-------|
| **ReplyTo Email** | Where replies go (e.g., a no-reply or support address) |
| **CC / BCC** | Comma-separated addresses; useful for sending a copy to the clinic |
| **Attachments** | Up to 5 files, 10 MB total; requires MIME type, name, and media URL |

### Critical: Wait For Setting

The Email node has two execution modes under **Advanced Options** — identical pattern to SMS:

| Mode | Behavior | Use in agent flows? |
|------|----------|---------------------|
| **Gateway Submit** | Node completes as soon as the message enters the email gateway queue | **Yes** — fast, stays under 30s |
| **Delivery Report** | Node waits for delivery/bounce confirmation | **No** — can take seconds to minutes, will timeout |

**Always set Wait For to "Gateway Submit"** in AI agent flows. Delivery Report mode blocks the flow waiting for email delivery confirmation, which regularly exceeds the 30-second agent timeout.

### Example: Appointment Confirmation Email with Prep Instructions

After `create_appointment` returns a confirmation number and `get_test_info` returned prep instructions, send an email before Flow Outcomes:

**Subject:**
```
Appointment Confirmed - $(n5.confirmation_number)
```

**Email Type:** HTML

**Message body:**
```html
<p>Hi $(n3.patient_first_name),</p>
<p>Your booking has been confirmed.</p>
<ul>
  <li><strong>Confirmation:</strong> $(n5.confirmation_number)</li>
  <li><strong>Date:</strong> $(n5.scheduled_at)</li>
  <li><strong>Test:</strong> $(n4.test_name)</li>
</ul>
<p><strong>Preparation:</strong> $(n4.prep_instructions)</p>
<p>Please arrive 15 minutes early with your insurance card and photo ID.</p>
```

- Node numbers reference earlier HTTP nodes — adjust via variable picker
- The Email fires on the HTTP POST node's **onSuccess** edge, same path as Flow Outcomes
- If Email fails, wire its **onError** edge directly to Flow Outcomes so the agent still gets the appointment data

### Exit Edges

| Edge | Trigger |
|------|---------|
| **onSuccess** | Message accepted by email gateway (Gateway Submit mode) |
| **onError** | Invalid destination, misconfigured email asset, gateway rejection |
| **onTimeout** | Expiry threshold exceeded (only relevant in Delivery Report mode) |

---

## RCS Messaging (Side-Effect Notifications)

Sends rich, app-like messages (rich cards with images, descriptions, and interactive buttons) to Android devices via RCS Business Messaging. RCS requires a two-node pattern: first check whether the recipient's device supports RCS, then send the message — with an SMS fallback if it doesn't.

### When to Use in AI Agent Flows

After an HTTP POST creates a record (appointment, order, etc.), use the RCS Capability + RCS Message nodes to send a rich card confirmation with interactive buttons (e.g., "View Details", "Cancel Appointment") before returning data through Flow Outcomes. Always include an SMS fallback path — not every device supports RCS.

```
Receive → HTTP GET → HTTP POST → RCS Capability → Branch (enabled?)
  → [Yes] → RCS Message → Flow Outcomes → End
  → [No]  → SMS → Flow Outcomes → End
```

### Node 1: RCS Capability Check

Verifies whether the recipient's device can receive RCS messages.

| Field | Value | Notes |
|-------|-------|-------|
| **Mobile Number** | Variable from flow (e.g., `$(n2.aiAgent.phone_number)`) | Use variable picker; must include country code |
| **Force Refresh** | `false` | Uses 7-day cached lookup; `true` forces live check (adds 3-6s latency — avoid in agent flows) |
| **Carrier** | *(leave blank)* | Only set if you know the customer's carrier code |

**Key output variables:**

| Variable | Purpose |
|----------|---------|
| `rcs.enabled` | Boolean — `true` if device has any RCS support |
| `rcs.version` | `up1` (basic), `up2` (rich cards/carousels), or `disabled` |
| `rcs.capabilities.richcard` | Boolean — `true` if device supports rich cards |

**Exit edges:** `onSuccess` (check completed) · `onError` (lookup failed)

### Node 2: Branch on RCS Support

After the capability check, add a Branch node to route the flow.

- **Input Variable**: `$(nX.rcs.enabled)` (where `nX` is the RCS Capability node)
- **Condition**: Equals `true` → route to RCS Message node
- **None of the above** → route to SMS fallback

For rich card support specifically, branch on `$(nX.rcs.capabilities.richcard)` equals `true`.

### Node 3: RCS Message

Sends the rich message to the recipient.

| Field | Value | Notes |
|-------|-------|-------|
| **Destination Type** | `MSISDN` | Mobile number |
| **Destination** | Variable from flow (e.g., `$(n2.aiAgent.phone_number)`) | Use variable picker; must include country code |
| **Message Type** | `Rich Card` | Also supports: Text, File, Carousel Card, Typing Indicator |

**Rich Card fields:**

| Field | Value | Notes |
|-------|-------|-------|
| **Card Orientation** | `Vertical` | Or Horizontal; Vertical is standard for confirmations |
| **Media Height** | `Medium` | Short, Medium, or Tall |
| **Media URL** | Image URL (e.g., company logo or location photo) | Max 2048 characters |
| **Title** | Card title with variables (e.g., `Appointment Confirmed`) | Max 200 characters |
| **Description** | Card body with variables | Max 2000 characters; insert variables via picker |
| **Suggestions** | Up to 4 interactive buttons per card | See suggestion types below |

**Suggestion types for buttons:**

| Type | Use Case |
|------|----------|
| **Simple Reply** | Quick-reply text back to agent (e.g., "Confirm") |
| **Open URL** | Link to a web page (e.g., appointment portal) |
| **Dial Phone** | Tap to call the location |
| **View Location** | Open map to location address |
| **Calendar Event** | Add appointment to device calendar |

### Critical: Wait For Setting

Same pattern as SMS and Email — under **Advanced Options**:

| Mode | Behavior | Use in agent flows? |
|------|----------|---------------------|
| **Gateway Submit** | Node completes as soon as the message enters the gateway queue | **Yes** — fast, stays under 30s |
| **Delivery Report** | Node waits for carrier delivery confirmation | **No** — will timeout |

**Always set Wait For to "Gateway Submit"** in AI agent flows.

### Timeout Warning

The two-node RCS pattern (Capability check → Branch → RCS Message or SMS) adds more nodes than a simple SMS side effect. All of them must complete within the 30-second agent flow timeout. Keep `Force Refresh` set to `false` on the Capability node (cached lookup is near-instant vs. 3-6s for live). If you're already chaining multiple HTTP nodes before the RCS side effect, test the full flow end-to-end to confirm it stays under 30 seconds.

### Example: Appointment Confirmation Rich Card

After `create_appointment` returns a confirmation number, send a rich card before Flow Outcomes:

**Message Type:** Rich Card

**Card Orientation:** Vertical · **Media Height:** Medium

**Title:**
```
Appointment Confirmed
```

**Description:**
```
Confirmation: $(n5.confirmation_number)
Date: $(n5.scheduled_at)
Test: $(n4.test_name)

Preparation: $(n4.prep_instructions)

Please arrive 15 minutes early with your insurance card and photo ID.
```

**Suggestions:**
1. **Open URL** — text: `View Details`, URL: `https://example.com/appointments`
2. **Dial Phone** — text: `Call Clinic`, phone: `+19105551234`
3. **Calendar Event** — text: `Add to Calendar`, title: `Lab Appointment`, start: `$(n5.scheduled_at)`

- Node numbers reference earlier HTTP nodes — adjust via variable picker
- Wire the RCS Message node's **onError** edge directly to Flow Outcomes so the agent still gets the appointment data even if the RCS message fails
- The SMS fallback branch should send the same core information (confirmation number, date, prep instructions) as plain text

### Exit Edges

| Edge | Trigger |
|------|---------|
| **onSuccess** | Message accepted by gateway (Gateway Submit mode) |
| **onError** | Invalid destination, RCS not supported (if capability check was skipped), gateway rejection |
| **onTimeout** | Expiry threshold exceeded (only relevant in Delivery Report mode) |

---

## Apple Messages for Business (Side-Effect Notifications)

Sends rich, interactive messages to iOS users via Apple Messages for Business. Supports interactive message types (rich links, list pickers, time pickers, forms) that render natively in the Messages app — no app install required.

### When to Use in AI Agent Flows

After an HTTP POST creates a record (appointment, order, etc.), drop an Apple Messages node between the last HTTP node and Flow Outcomes to send a rich confirmation. Unlike SMS, the customer must have an **active session** — they must have messaged your business first. This makes it ideal for flows triggered by an inbound customer interaction (e.g., a contact center call or chat), but it cannot cold-send to a phone number.

```
Receive → HTTP GET → HTTP POST → Apple Messages → Flow Outcomes → End
```

### Key Constraint: Active Session Required

Apple Messages for Business requires the customer to have initiated a conversation with your business first. You cannot send outbound messages to arbitrary phone numbers like SMS. If no active session exists, the node will fail. Always wire the **onError** edge to Flow Outcomes so the agent still returns data even if the Apple Message cannot be delivered.

### Required Configuration

| Field | Value | Notes |
|-------|-------|-------|
| **Destination Type** | `User ID` | Apple Messages user identifier |
| **Destination** | Apple Messages for Business ID from the session | Use variable picker |
| **Message Type** | See interactive types below | Select based on use case |
| **Wait For** | `Gateway Submit` | Same pattern as SMS/Email/RCS — never use Delivery Report in agent flows |
| **Expiry** | `Seconds` with reasonable duration | Or `UTC` with a specific date |

### Interactive Message Types

| Type | What It Does | When to Use in Agent Flows |
|------|-------------|---------------------------|
| **Rich Link** | Displays a URL preview card with image, title, and tap-to-open link | Appointment confirmation linking to a portal or directions page |
| **List Picker** | Shows a scrollable list of items the customer can select from (up to 20 sections × 20 items) | Let the customer pick from available time slots or test types mid-flow |
| **Time Picker** | Presents selectable time slots with location details (title, lat/long) | Appointment scheduling — show 3-5 available slots with the clinic location |
| **Form Message** | Multi-page structured form with typed input fields | Collect patient intake information or insurance details |

### Rich Link Fields

| Field | Value | Notes |
|-------|-------|-------|
| **URL** | Link to open on tap | e.g., appointment portal URL |
| **Title** | Display title (max 128 chars) | e.g., `Appointment Confirmed - $(n5.confirmation_number)` |
| **Image URL** | Preview image | Company logo or location photo |
| **MIME Type** | Image MIME type | e.g., `image/png` |

### List Picker Fields

| Field | Value | Notes |
|-------|-------|-------|
| **Title / Subtitle** | Bubble text shown before customer taps | e.g., `Select a Time Slot` |
| **Sections** | Grouped items (max 20 sections, 20 items each) | Each item has title, subtitle, and identifier |
| **Multi-select** | Toggle on/off | Off for single-selection scenarios like picking one time slot |
| **Request Identifier** | Unique string to correlate the reply | Use a flow variable or hardcoded action name |

### Time Picker Fields

| Field | Value | Notes |
|-------|-------|-------|
| **Title** | Picker header | e.g., `Available Appointments` |
| **Time Slots** | Up to 10 slots, each with start time, duration (seconds), and identifier | Past time slots are automatically hidden by Apple |
| **Location** | Title, latitude, longitude, radius | Clinic address for context |
| **Request Identifier** | Unique string to correlate the reply | Same pattern as List Picker |

### Critical: Wait For Setting

Same pattern as SMS, Email, and RCS — under **Advanced Options**:

| Mode | Behavior | Use in agent flows? |
|------|----------|---------------------|
| **Gateway Submit** | Node completes as soon as the message enters the gateway queue | **Yes** — fast, stays under 30s |
| **Delivery Report** | Node waits for delivery confirmation | **No** — will timeout |

**Always set Wait For to "Gateway Submit"** in AI agent flows.

### Example: Appointment Confirmation as Rich Link

After `create_appointment` returns a confirmation number, send a rich link before Flow Outcomes:

**Message Type:** Rich Link

**Title:**
```
Appointment Confirmed - $(n5.confirmation_number)
```

**URL:**
```
https://example.com/appointments/$(n5.confirmation_number)
```

**Image URL:** `https://example.com/assets/clinic-logo.png`

**MIME Type:** `image/png`

- Node numbers reference earlier HTTP nodes — adjust via variable picker
- Wire the Apple Messages node's **onError** edge directly to Flow Outcomes so the agent still gets the appointment data if the message fails (e.g., no active session)
- Consider an SMS fallback for customers not on iOS or without an active Apple Messages session

### Exit Edges

| Edge | Trigger |
|------|---------|
| **onSuccess** | Message accepted by gateway (Gateway Submit mode) |
| **onError** | No active session, invalid destination, gateway rejection |
| **onTimeout** | Expiry threshold exceeded (only relevant in Delivery Report mode) |

---

## WhatsApp (Side-Effect Notifications)

Sends a WhatsApp message to a customer via the configured WhatsApp asset. In AI agent flows, use it as a **side effect** — fire-and-forget confirmation after the core API work is done, before returning data through Flow Outcomes.

Two message modes: **template messages** (proactive — works anytime, requires pre-approval from Meta) and **session messages** (replies within the 24-hour window after the customer last messaged). For agent flow side effects, **template messages** are recommended because the 24-hour window status is unpredictable.

### Flow Pattern

```
Receive → HTTP GET → HTTP POST → WhatsApp → Flow Outcomes → End
```

### Key Constraint: 24-Hour Window

WhatsApp enforces a 24-hour session window from the customer's last message. Free-form messages (text, media, interactive) only work within this window. Outside the window, only **template messages** are allowed. Since agent flows are triggered by customer interactions, a session window is typically open — but for reliability, use template messages for side-effect confirmations.

### Required Fields

| Field | Value | Details |
|-------|-------|---------|
| **Destination Type** | `WA ID` | WhatsApp ID (phone number with country code) |
| **Destination** | WhatsApp ID | Use variable picker: `$(n2.aiAgent.phone_number)` |
| **Message Type** | `Template` or `Text` | Template for reliability outside 24hr window |

### Template Message Configuration

| Field | Details |
|-------|---------|
| **Template Name** | Select from approved templates dropdown |
| **Header Parameters** | Map via variable picker if template has header variables |
| **Body Parameters** | Map via variable picker: `$(n3.confirmation_number)`, `$(n3.appointment_date)`, etc. |

### Text Message Configuration (Within 24hr Window)

| Field | Details |
|-------|---------|
| **Message** | Max 4,096 characters. Supports `*bold*`, `_italic_`, `~strikethrough~`, `` `monospace` `` |
| **Preview URL** | Optional — renders first URL as clickable preview |

### Wait For

| Mode | Agent Flows? |
|------|-------------|
| **Gateway Submit** | **Yes** — fast, recommended |
| **None** | Yes — no delivery confirmation |
| **Delivery Report** | No — too slow for 30-second timeout |
| **Read** | No — privacy settings may block |

**Always use Gateway Submit** in agent flows.

### Exit Paths

| Event | When |
|-------|------|
| `onSuccess` / `onSubmit` | Message accepted by WhatsApp |
| `onError` | Invalid destination, template mismatch, configuration error |
| `onPolicyFail` | Contact policy or expiry restriction |
| `onDeliveryReportFail` | Delivery/read receipt not received within timeout |

### Output Variables

| Variable | Description |
|----------|-------------|
| `send.deliveryStatusCode` | Numeric status code |
| `send.deliveryStatusDescription` | Status description |
| `send.gatewayTid` | Transaction ID |

### Example: Appointment Confirmation via Template

```
Receive → HTTP POST (create appointment) → WhatsApp (Template: appointment_confirmed) → Flow Outcomes → End
```

Configure the WhatsApp node:
- Destination Type: WA ID
- Destination: `$(n2.aiAgent.phone_number)` (variable picker)
- Message Type: Template
- Template: `appointment_confirmed`
- Body Parameter 1: `$(n3.patient_name)` — patient name from POST response
- Body Parameter 2: `$(n3.appointment_date)` — date from POST response
- Body Parameter 3: `$(n3.confirmation_number)` — confirmation from POST response
- Wait For: Gateway Submit

Wire **onError** to Flow Outcomes so the agent still returns data if the WhatsApp message fails.

### Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Template not in dropdown | Not approved by Meta | Check status in Tools > Templates; allow 24-72 hrs |
| Error 7710 | Free-form message outside 24-hour window | Use template message instead |
| Parameter mismatch (7804) | Template body expects N params but fewer provided | Match parameter count exactly |
| Variable arrives empty | Typed manually | Use variable picker |
| Message not delivered | Customer not on WhatsApp (7865) | Consider SMS fallback |

Full WhatsApp reference: `connect-whatsapp.md`.

---

## Voice Nodes (Voice Node Group)

The following nodes live exclusively inside the Voice Node Group. They are used in voice call flows (Start/Call User pattern), NOT in AI Agent action flows.

---

## Call Patch Node (Voice Node Group)

Bridges the ongoing call (A-party) with another number (B-party) inside the Voice Node Group. Used for two-party conferencing — dials the B-party, plays optional audio to both parties during connection, then merges the calls.

### When to Use

- Transfer a caller to a live agent or specialist while keeping the flow in control
- Conference two parties (e.g., caller + on-call technician) during an automated voice flow
- Patch a caller through to a destination with jingle/hold audio and optional recording

**Not for AI agent action flows.** This node lives inside a Voice Node Group, which only exists in outbound/inbound voice call flows (Start/Call User pattern), not in AI Agent Event flows.

### Configuration

| Field | Value | Notes |
|-------|-------|-------|
| **Destination (B-PARTY)** | E.164 phone number or variable | Format errors exit through ErrorEdge |
| **Display Number** | Select from provisioned voice numbers (Assets) | Number shown to B-party as caller ID |
| **Display Name** | Business name (max 10 characters) | Must be enabled by account manager |
| **Play Audio** (toggle) | Enable/disable pre-patch audio | Controls the two audio fields below |
| **Play audio to A party** | Jingle file played to caller during patch attempt | Keeps caller informed while B-party rings |
| **Play audio to B party** | Announcement file played to B-party before merge | e.g., "You have an incoming patched call" |
| **Announcement loop** | Repeat announcement until DTMF keypress or threshold | Configurable loop threshold prevents infinite playback |
| **Transfer DTMFs** | Forward DTMF keypresses between parties post-patch | Enable if B-party needs to hear caller's key presses |
| **Record the call** | Save recording to Voice Recordings | Configure a file prefix; files appear in Tools > Voice Recordings |

### Exit Paths

| Edge | Color | Trigger |
|------|-------|---------|
| **onSuccess** | Green | Call successfully patched — both parties connected |
| **onNoAnswer** | Yellow | B-party does not answer, or announcement loop threshold reached without DTMF |
| **onError** | Red | Patching error (e.g., invalid E.164 format on destination) |

### Output Variables

| Variable | Description |
|----------|-------------|
| `patch.APartyNumber` | Originating number (A-party / caller) |
| `patch.BPartyNumber` | Destination number (B-party) |

### Example: Patch Caller to On-Call Technician

```
Start (Inbound Call) → Voice Node Group
  → IVR Menu ("Press 1 for emergency dispatch")
    → [1] → Call Patch (destination: on-call number, jingle to A-party, announcement to B-party)
      → onSuccess → Play ("You are now connected") → End
      → onNoAnswer → Play ("No technician available, please try again later") → End
      → onError → Play ("We encountered an error") → End
```

### Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| onError fires immediately | Destination not in E.164 format | Include `+` and country code (e.g., `+15551234567`) |
| B-party hears nothing before patch | "Play audio to B party" not configured or toggle off | Enable Play Audio and set the announcement file |
| Announcement loops forever | Loop threshold not set | Configure the announcement loop threshold |
| No recording saved | "Record the call" not enabled, or missing file prefix | Enable recording and set an alphanumeric prefix |

---

## Call Transfer Node (Voice Node Group)

Transfers the active call to a specified phone number. Supports two modes: **blind transfer** (disconnect immediately when transferee rings) and **warm transfer** (disconnect when transferee answers, with a failure path if unanswered). Lives inside the Voice Node Group.

### When to Use

- Hand off a call to an external number (e.g., specialist, clinic, department) without maintaining the connection
- Blind transfer when Connect does not need to track the outcome
- Warm transfer when you need a fallback path if the transfer fails

**Not for AI agent action flows.** Voice Node Group only.

### Availability Restrictions

- **Available only on request** — contact your account manager to enable this node on your tenant
- **Not available in London or Europe regions** — this feature is region-restricted

### Configuration

| Field | Value | Notes |
|-------|-------|-------|
| **Play Audio** | Optional audio before transfer begins | Configure per Play node pattern (TTS, file, URL) |
| **To Number** | E.164 phone number or variable | Format errors exit through ErrorEdge |
| **Transfer Type** | `Blind` or `Warm` | See behavior differences below |

### Transfer Type Behavior

| Type | When Connect Disconnects | Failure Handling |
|------|--------------------------|-----------------|
| **Blind** | When the call starts **ringing** at the transferee's end | No failure path — Connect has already disconnected |
| **Warm** | When the transferee **answers** | If unanswered, exits via `TransferFailed` edge — flow can continue |

### Exit Paths

| Edge | Trigger |
|------|---------|
| **ErrorEdge** | To Number not in valid E.164 format |
| **TransferFailed** | Warm transfer only — transferee did not answer |

**Note:** Blind transfers have no TransferFailed edge because Connect disconnects at ring time. If the transferee doesn't answer a blind transfer, the caller hears ringing until they hang up — Connect has no visibility.

### Example: Warm Transfer to Specialist with Fallback

```
Start (Inbound Call) → Voice Node Group
  → Play ("Transferring you to a specialist, please hold")
  → Call Transfer (To Number: +15559876543, Type: Warm)
    → TransferFailed → Play ("The specialist is unavailable. Returning to main menu.") → IVR Menu
    → ErrorEdge → Play ("We encountered an error with the transfer") → End
```

### Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Node not in palette | Not enabled on tenant | Contact account manager to enable |
| Node unavailable | Tenant in London or Europe region | Not supported in these regions — use Call Patch as alternative |
| ErrorEdge fires immediately | To Number not in E.164 format | Include `+` and country code |
| Caller hears ringing forever (blind) | Normal blind transfer behavior — Connect disconnects at ring | Use warm transfer if you need a failure path |
| TransferFailed never fires | Transfer Type set to Blind | TransferFailed only exists for Warm transfers |

---

## Record Node (Voice Node Group)

Records audio from the caller during an active voice call. The recording is saved to Voice Recordings (Tools > Voice Recordings) with a configurable file prefix. Lives inside the Voice Node Group.

### When to Use

- Capture a voicemail message when no agent is available
- Record a caller's verbal statement (e.g., incident description, authorization consent)
- Log a call segment for compliance or quality purposes

**Not for AI agent action flows.** Voice Node Group only.

### Configuration

| Field | Value | Notes |
|-------|-------|-------|
| **Play Audio** (toggle) | Optional prompt before recording starts | e.g., "Please leave your message after the beep" |
| **Play short beep before starting the recording** | Checkbox | Auditory cue signaling recording has begun |
| **Recording Timeout (in seconds)** | Max recording duration | Maximum value: **300 seconds** (5 minutes) |
| **Stop Recording on Keypress** | DTMF key that ends recording | e.g., `#` — caller presses to stop early |
| **Audio File Prefix Name** | Prefix for saved recording files | Alphanumeric, underscores, `$` signs, or variables |

### Exit Paths

| Edge | Color | Trigger |
|------|-------|---------|
| **onSuccess** | Green | Recording completed (caller pressed stop key or finished speaking) |
| **onrecordingTimeout** | Yellow | Recording hit the configured timeout duration |
| **onError** | Red | Recording failed |

### Output Variables

| Variable | Description |
|----------|-------------|
| `record.recordingFilePath` | Path to the saved recording file in Voice Recordings |

### Example: Voicemail After No Answer

```
Call User → onNoAnswer → Voice Node Group
  → Play ("The person you are calling is unavailable. Please leave a message after the beep.")
  → Record (timeout: 120s, stop key: #, prefix: voicemail)
    → onSuccess → Play ("Your message has been recorded. Goodbye.") → End
    → onrecordingTimeout → Play ("Recording limit reached. Goodbye.") → End
    → onError → Play ("We could not record your message. Please try again later.") → End
```

### Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Recording cuts off too early | Timeout set too low | Increase Recording Timeout (max 300 seconds) |
| No beep before recording | Checkbox not enabled | Enable "Play short beep before starting the recording" |
| Recording file not found | Missing or invalid Audio File Prefix Name | Set a valid alphanumeric prefix |
| Caller can't stop recording | Stop Recording on Keypress not configured | Set a DTMF key (e.g., `#`) |
