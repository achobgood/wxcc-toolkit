# Webex Connect — Platform Reference

<!-- ref-tag: webex-connect-v1 -->

## Flow Structure for AI Agent Actions

Every AI agent action maps to exactly one Webex Connect flow. The flow follows this pattern:

```
Receive (AI Agent Event) -> HTTP Request Node(s) -> Flow Outcomes -> End
```

### Required Nodes

- **Receive node** (always first): listens for the AI Agent Event
- **HTTP Request node(s)**: calls the backend API (REST endpoint)
- **Flow Outcomes node**: returns data back to the AI agent
- **End node**: terminates the flow

### Prohibited Nodes in AI Agent Flows

These nodes cause 30-second timeouts and break the agent. Never use them:

- **Delay** -- introduces wait time the agent cannot tolerate
- **Social Hour** -- time-based routing that stalls the flow
- **Receive** (second instance after the initial one) -- creates a blocking listener
- **Call Workflow** -- hands off to another flow, exceeding timeout

### Safe Non-HTTP Nodes for AI Agent Flows

These nodes execute fast and are safe within the 30-second timeout:

- **Branch** -- conditional routing (check HTTP status codes)
- **Evaluate** -- inline JavaScript (date conversion, string ops)
- **Data Parser** -- JSON field extraction (when HTTP node parsing isn't enough)
- **Customer Journey Data** -- JDS reads/writes (keep lightweight)
- **SMS** -- side-effect notifications (use Gateway Submit mode, not Delivery Report)
- **Email** -- side-effect notifications (use Gateway Submit mode, not Delivery Report)
- **RCS** -- rich side-effect notifications (requires Capability check + Branch fallback to SMS; use Gateway Submit mode)
- **Apple Messages** -- rich side-effect notifications for iOS users (requires active customer session; use Gateway Submit mode)

See `webex-connect-advanced.md` for configuration details on all non-HTTP nodes.

---

## Receive Node Configuration

1. Add a **Receive** node from the palette
2. Set **Event Source**: AI Agent
3. Set **Event Name**: must match the action name in AI Agent Studio exactly (case-sensitive)
4. Under **Input Variables**, add one row per slot entity the action declares

---

> **Connect vs. Flow Designer HTTP:** This section covers the Webex Connect HTTP Request node used in AI agent action flows, notification flows, and digital inbound flows. For calling WxCC APIs from Flow Designer voice flows with managed authentication, see the **HTTP Connector** section in `docs/reference/wxcc-platform.md`.

## HTTP Request Node -- GET Requests

### URL Format

```
https://{api-base-url}/{endpoint}?{filters}
```

Use the **variable picker** (click, don't type) to insert AI Agent variables into the URL:

```
...?phone_number=eq.$(n2.aiAgent.phone_number)
```

Node numbers change based on flow layout -- always use the picker to get the correct reference.

### Headers

Configure headers appropriate to your backend API. Common headers include:

| Header | Purpose |
|--------|---------|
| Auth header(s) | API key, Bearer token, etc. |
| `Content-Type` | `application/json` |
| `Accept` | Controls response format (single object vs. array) -- backend-specific |

### Output Variables Tab

1. Paste a **sample JSON response** into the Parse field and click **Parse** -- rows auto-generate
2. **Rename `id`** to a descriptive name (e.g., `customer_id`, `order_id`) to avoid collision when chaining multiple HTTP nodes
3. Response path format depends on response shape:
   - **Single object**: `$.field_name`
   - **Array -- first element**: `$[0].field_name`
   - **Array -- whole array**: `$`

---

## HTTP Request Node -- POST Requests

For create/update operations:

### Method: POST

### Additional Headers

If your backend supports it, add a header to return the created record in the response. For example, PostgREST-compatible APIs use:

```
Prefer: return=representation
```

This returns the created record so you can capture auto-generated IDs, confirmation numbers, etc.

### Body

- Set body type to **JSON**
- Use the **variable picker** to insert values from previous HTTP nodes or AI agent entities
- Example body referencing a previous node's output and AI agent slot entities:

```json
{
  "customer_id": "$(n3.customer_id)",
  "location_id": "hardcoded-known-uuid",
  "item_id": "$(n2.aiAgent.item_id)",
  "scheduled_at": "$(n2.aiAgent.scheduled_at)",
  "status": "active"
}
```

---

## HTTP Request Node -- PATCH Requests

For updating existing records (reschedule, cancel, status changes).

### Method: PATCH

### URL

Include filters to target the specific record:

```
https://{api-base-url}/{table}?{unique_filter}
```

Example -- cancel a record by ID:

```
/rest/v1/{table}?id=eq.$(n3.record_id)
```

### Headers

Same as POST, including `Prefer: return=representation` to get the updated record back.

### Body

Only include the fields being changed:

```json
{
  "status": "cancelled"
}
```

Use the variable picker for dynamic values:

```json
{
  "scheduled_at": "$(n2.aiAgent.new_scheduled_at)",
  "status": "rescheduled"
}
```

### Two-Node Pattern: Lookup Then Update

Most PATCH actions require two HTTP nodes — the caller provides a human-speakable identifier (phone number, confirmation number), but PATCH needs the record's primary key.

```
Receive → HTTP GET (lookup by phone/confirmation) → HTTP PATCH (update by ID) → Flow Outcomes → End
```

- **Node 1 (GET)**: Look up the record using the caller's identifier. Output the record's `id`.
- **Node 2 (PATCH)**: Update using `$(n{node1}.record_id)` in the filter URL.

---

## HTTP Request Node -- PUT Requests

For full-record replacement (overwrite all fields on an existing record).

### Method: PUT

### URL

Include filters to target the specific record, same pattern as PATCH:

```
https://{api-base-url}/{table}?{unique_filter}
```

### Headers

Same as POST/PATCH, including `Prefer: return=representation` if supported by your backend.

### Body

Include **all fields** for the record — PUT replaces the entire resource, unlike PATCH which updates only specified fields:

```json
{
  "customer_id": "$(n3.customer_id)",
  "location_id": "hardcoded-known-uuid",
  "item_id": "$(n2.aiAgent.item_id)",
  "scheduled_at": "$(n2.aiAgent.new_scheduled_at)",
  "status": "rescheduled",
  "notes": "$(n2.aiAgent.notes)"
}
```

### PUT vs PATCH

| Method | Behavior | When to Use |
|--------|----------|------------|
| **PATCH** | Updates only the fields you send | Most update operations — changing status, rescheduling |
| **PUT** | Replaces the entire record with what you send | Full-record rewrites where omitted fields should be cleared |

**Default to PATCH** for AI agent actions. PUT is available if the backend API requires it, but PATCH is safer — you won't accidentally null out fields you forgot to include.

---

## Variable Picker

### Format

```
$(n{nodeNumber}.aiAgent.{entity_name})
```

- `n{nodeNumber}` -- the Receive node number (changes based on flow layout)
- `aiAgent` -- indicates the variable came from the AI agent
- `{entity_name}` -- the slot entity name

### Rules

- **NEVER type variable references manually** -- always use the variable picker (click the variable icon in the URL or body field)
- Manually typed variables will arrive empty at runtime with no error
- The picker auto-generates the correct `$(nX.variableName)` syntax

### Referencing Previous Node Output

When chaining HTTP nodes, reference output variables from an earlier node:

```
$(n{nodeNumber}.{variableName})
```

Note: no `aiAgent` prefix -- this is a direct node output reference, not an AI agent entity.

---

## Variable Naming Rules

Connect variable names allow: **alphabets, numerics, underscores, hyphens, spaces**

Use lowercase underscores consistently:

- `customer_first_name` -- recommended
- `customerFirstName` -- avoid (camelCase inconsistent with Connect conventions)
- `customer-first-name` -- allowed but inconsistent with underscore convention

---

## Flow Outcomes Node

**Critical:** Always use **key-value mode**, NOT Enter JSON mode.

Enter JSON mode does NOT resolve variables -- it returns literal strings like `$(n3.customer_id)` instead of the actual value. This is a platform bug/limitation with no workaround other than using key-value mode.

### Configuration Steps

1. Add a **Flow Outcomes** node after the last HTTP node
2. Open **Flow Settings > Flow Outcomes**
3. Under **Last Execution Status**: toggle **Notify AI Agent** to **ON**
4. In the Flow Outcomes node itself, switch to **key-value mode**
5. Add one row per variable to return to the AI agent:
   - **Key**: the name the AI agent will reference (e.g., `customer_first_name`)
   - **Value**: use the **variable picker** to select from HTTP node output

### Notify AI Agent Toggle

This toggle is in **Flow Settings > Flow Outcomes > Last Execution Status**. If it is OFF, the AI agent will never receive the flow's response data. This is a separate setting from the Flow Outcomes node itself.

---

## Configure AI Agent Event (Sample JSON)

Every action requires a sample JSON payload configured in **Webex Connect** — specifically in the flow's **Receive node**. Double-click the Receive node, click **Configure AI Agent Event**, and paste the JSON. This tells Connect what shape of data to expect from the agent.

### Format

```json
{
  "phone_number": "5551234567",
  "preferred_date": "2026-03-15"
}
```

### Rules

- One key per slot entity the action declares
- Use realistic example values (actual test data works well)
- Keys must match the entity names in AI Agent Studio exactly

---

## Chaining Multiple HTTP Nodes

One action = one Connect flow, but you can chain multiple HTTP Request nodes inside a single flow when an action requires multiple API calls (e.g., look up a customer ID, then create a record using that ID).

### How to Chain

1. Add a second HTTP Request node after the first
2. Wire first node's **Success** output to the second node's input
3. Reference output variables from the first node in the second node's URL or body using the variable picker
4. Variable format from a previous node: `$(n{nodeNumber}.{variableName})`

### Example: Two-Node Flow

- **Node 3** (GET): Looks up customer by phone number, outputs `customer_id`
- **Node 5** (POST): Creates a record using `$(n3.customer_id)` in the body

---

## Common URL Patterns (Generic REST/PostgREST)

| Operation | URL Pattern |
|-----------|-------------|
| Exact match lookup | `/{table}?{column}=eq.$(n2.aiAgent.{entity})` |
| Fuzzy text search | `/{table}?{column}=ilike.*$(n2.aiAgent.{entity})*` |
| Date range filter | `/{table}?{date_col}=gte.{start}&{date_col}=lte.{end}` |
| Sort + limit | `&order={column}.asc&limit=3` |
| Hardcoded filter | `/{table}?{column}=eq.{known_uuid}` |

---

## Testing a Flow

Before wiring a flow to an AI agent action:

1. Use **curl** (or any HTTP client) to test the raw API URL with the same headers
2. Verify the response shape matches what your output variables expect
3. In Connect, use **Test Flow** (if available) or trigger via a test AI agent session in AI Agent Studio

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Variable arrives empty in URL | Variable not substituted -- typed manually instead of using picker | Use variable picker, never type manually |
| `401` error | Auth headers missing or malformed (e.g., missing space after `Bearer`) | Verify auth headers exactly match API requirements |
| `400` error | Wrong filter column or invalid query syntax | Check URL -- ensure filter column matches actual DB column name |
| `406` error | Single-object Accept header used but query returned 0 rows | Remove single-object Accept header, or fix filter to match a row |
| Flow Outcomes variables show as literal strings | Using Enter JSON mode instead of key-value mode | Switch to key-value mode in Flow Outcomes node |
| Array response breaks output variables | Using single-object Accept header with an array response | Remove the single-object Accept header |
| 30-second timeout in agent flow | Prohibited node type in use (Delay, Receive x2, Social Hour, Call Workflow) | Remove the prohibited node |
| Output variable name collision | Multiple HTTP nodes both have a variable named `id` | Rename `id` to descriptive names (e.g., `customer_id`, `order_id`) after parsing |
| Flow never triggers | Event Name in Receive node does not match action name in AI Agent Studio | Ensure exact case-sensitive match |
| Notify AI Agent is OFF | Flow runs but agent never receives data | Toggle ON in Flow Settings > Flow Outcomes > Last Execution Status |
| HTTP 4xx/5xx doesn't trigger onError edge | HTTP errors go through **onSuccess** (the request completed). onError is for connection failures. | Branch on `$(nX.https.statusCode)` after the HTTP node. See `webex-connect-advanced.md` for the Branch node pattern. |

---

## Custom Nodes (Webex API Integration)

Custom Nodes let you call Webex platform APIs (People, SCIM2, Calling) from Connect flows with **managed OAuth** — no manual Bearer tokens or refresh logic. Connect handles the full OAuth lifecycle (authorization code grant, token refresh) transparently.

**Token refresh mechanism:** When you configure OAuth on the Custom Node, you set the **Refresh URL Token** and enable **"Access token has a limited validity"** with the token's lifespan. Connect tracks the token validity internally and automatically calls the Refresh URL Token endpoint to obtain a new access token when the current one expires. The official Cisco documentation for Email assets states: *"Token has a fixed expiry time and the backend application automatically calls the API to regenerate token before that."* The Custom Node docs do not specify whether this refresh is a background process or triggered at call time — treat it as platform-managed and opaque. Each refresh also resets the refresh token's 90-day expiry, so the integration stays authorized indefinitely as long as the refresh token is used before it expires.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes); [Email - WXCC](https://help.webexconnect.io/docs/wxcc-email-asset-creation)]

### When to Use Custom Nodes vs Raw HTTP

| Scenario | Use |
|----------|-----|
| Calling your own backend (Supabase, custom API) | Raw HTTP Request node with API key |
| Calling Webex APIs (People, Calling, SCIM2) | Custom Node with OAuth — token refresh handled automatically |
| Calling WxCC APIs (CC Config, Search) | Either — but raw HTTP with a stored token works fine for simple calls |

### Prerequisites

| Requirement | Details |
|-------------|---------|
| Webex Integration | Created at developer.webex.com (NOT a Service App — Integrations support Authorization Code grant) |
| Redirect URI | Don't guess — create the Custom Node first (Step 2 below), then copy the **Call Back URL** from the OAuth config. US example: `https://oauth.us.webexconnect.io/callback`. See regional patterns in the Configure Authorization section below. |
| Scopes | API-specific (e.g., `spark-admin:people_read`) plus `spark:kms` |

### Create the Webex Integration

1. Go to **developer.webex.com** → avatar → **My Webex Apps** → **Create a New App** → **Integration**
2. Set **Will this integration use a mobile SDK?** to **No**
3. Set **Redirect URI** to `https://oauth.us.webexconnect.io/callback`
4. Select required **Scopes** (e.g., `spark-admin:people_read`, `spark:kms`)
5. Record **Client ID** and **Client Secret**

### Create the Custom Node

1. In Webex Connect: **Assets → Integrations → Add Integration → Custom Node**

| Field | Value |
|-------|-------|
| **Creation type** | From blank (or copy an existing node) |
| **API Integration Type** | REST (or SOAP — use REST for Webex APIs) |
| **Node name** | Descriptive name (e.g., "Webex People Lookup") |
| **Description** | Optional — what this node does |
| **Node category** | Choose or create a category (e.g., "Webex APIs") |
| **Node icon** | Optional SVG file (64×64 pixels) |

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Add a Request Method

Each Custom Node supports **up to 25 distinct request methods** (limit enforced from v5.6.0). Each method has its own independent authorization config, URL, parameters, and response mapping — authorization does NOT inherit from one method to another. Different methods on the same node can use different auth types (e.g., method 1 uses OAuth 2.0, method 2 uses Basic Auth).

When the Custom Node is placed on the flow canvas, the user selects which method to invoke via a **"Method Name" dropdown** in the node configuration dialog.

Example: "GetPersonByEmail" for the People API.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes-integration)]

| Field | Value |
|-------|-------|
| **Method name** | GetPersonByEmail |
| **Type** | GET |
| **Resource URL** | `https://webexapis.com/v1/people` |
| **Request Timeout** | 2000ms |
| **Connection Timeout** | 2000ms |

### Configure Authorization

Custom Nodes support four authorization types: **OAuth 2.0**, **Basic Auth**, **Digest Auth**, and **AWS Signature**. This section covers OAuth 2.0 (the most common for Webex APIs). For other types see [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes).

In the method's **Authorization** section:

| Field | Value |
|-------|-------|
| **Type** | OAuth 2.0 |
| **Grant Type** | Authorization Code — see Grant Type note below |
| **Consumer ID** | Integration Client ID (from Step 1) |
| **Consumer Secret** | Integration Client Secret (from Step 1) |
| **Call Back URL** | Auto-populated by Connect — copy this and register it in your OAuth provider's redirect URI list |
| **Authorization URL** | `https://webexapis.com/v1/authorize` |
| **Scopes** | Space-separated scope list (e.g., `spark-admin:people_read spark:kms`) |
| **Access Token URL** | `https://webexapis.com/v1/access_token` |
| **Access Token URL Method** | POST (default for Webex) |
| **Access Token URL Parameter type** | Body (or URL — depends on provider) |
| **Access Token URL Headers** | Leave blank unless the provider requires additional headers |
| **Access token has a limited validity** | Checked (enabled) |
| **Validity** | `14` days (Webex OAuth access token lifespan) |
| **Refresh URL Token** | `https://webexapis.com/v1/access_token` |
| **Client Authentication** | Send client credentials in body (default — correct for Webex) |

After filling in these fields, click **Authorize** (or **Get Access Token**). A **browser popup window** opens:

1. The popup navigates to the **Authorization URL** you configured (for Webex: the Webex login page)
2. The user signs in with their Webex account (if not already logged in)
3. A **scope consent screen** appears showing the requested permissions — the user clicks **Accept**
4. The popup redirects to the Call Back URL (handled by Connect's server) and **closes automatically**
5. Back in the Custom Node config, the **Access Token** and **Refresh Token** fields auto-populate

If the popup is blocked by the browser, authorization will fail silently — ensure popups are allowed for the Connect domain. If authorization fails, the third-party provider's error message is displayed in the popup.

> **Grant Type — when to use which:**
> - **Authorization Code**: use for APIs that issue tokens in the context of a user (requires browser popup for consent). **Webex APIs only support Authorization Code** — they do not accept `grant_type=client_credentials`. If you are calling Webex APIs (People, SCIM2, Calling), you must use Authorization Code.
> - **Client Credentials**: use for third-party APIs that support machine-to-machine tokens without user context (no browser popup needed). Only use this if the target API provider explicitly supports it (e.g., some ServiceNow, Salesforce configurations).
>
> **Client Authentication options:** Two choices — "Send client credentials in body" (default, sends `client_id` and `client_secret` as POST body parameters) and "Send as Basic Auth header" (sends `Authorization: Basic <base64(client_id:client_secret)>` header). Webex supports both; use the default ("Send client credentials in body") — this matches all Cisco example code.
>
> **`spark:kms` scope:** Required for key management. Always include it alongside your functional scopes.
>
> **Validity field:** This tells Connect when to refresh. Set it to match the actual access token lifespan (14 days for Webex OAuth tokens).
>
> **Refresh URL Token:** Connect uses this endpoint to obtain a new access token when the current one expires. For Webex, it's the same endpoint as the Access Token URL.
>
> **Call Back URL — regional variations:** The callback URL is auto-populated based on your Connect data center. The pattern is `https://oauth.[tenantName].[region].webexconnect.io/callback`. Known regions: `us` (Oregon/AWS), `us1` (USA/Azure), `eu` (Ireland), `uk` (London), `ca` (Canada), `in` (Mumbai), `au` (Sydney), `sg` (Singapore). You must register this exact URL in your OAuth provider's redirect URI list.
>
> **Re-authorization triggers:** If you edit the OAuth config in the admin portal, you will be prompted to re-authorize. If credentials are updated in the integrating system, Connect loses access and users must re-authorize manually. Existing integrations are not impacted until the Refresh Token expires or you decide to reauthorize.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes); [Custom Nodes Integration](https://help.webexconnect.io/docs/custom-nodes-integration); [Webex Integrations and Authorization](https://developer.webex.com/docs/api/guides/integrations-and-authorization); [Product Update July 2022](https://help.webexconnect.io/changelog/product-update-july-2022)]

### Configure Security (Optional)

If the target API requires mutual TLS or a specific SSL/TLS version:

**Key Store** (client certificate):

| Field | Value |
|-------|-------|
| **Browse Certificate** | Upload your key store certificate file |
| **Select File Format** | JKS or PKCS12 |
| **Store Password** | Password to access the store |
| **Key Password** | Password to access the key |
| **Name** | Descriptive name for the certificate |

**Trust Store** (server certificate):

| Field | Value |
|-------|-------|
| **Browse Certificate** | Upload the trust store certificate file |
| **Select File Format** | JKS or PKCS12 |
| **Store Password** | Password to access the store |

**Security Protocol options:** SSL 2.0, SSL 3.0, TLS 1.0, TLS 1.1, TLS 1.2. Use TLS 1.2.

> For standard Webex API calls, skip this section — no client certificates needed.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Define Header Parameters

Add any custom headers the API requires beyond what OAuth provides:

| Parameter | Parameter Value Type | Value / Field Name |
|-----------|---------------------|-------------------|
| `Content-Type` | Static | `application/json` |

- **Static** parameters have a fixed value set here
- **Dynamic** parameters create an input field on the node — the flow passes a value at runtime

> The `Authorization: Bearer <token>` header is injected automatically by Connect — do not add it manually.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Define URL Parameters

| Parameter | Parameter Value Type | Value / Field Name |
|-----------|---------------------|-------------------|
| `email` | Dynamic | Field name: "email" (passed from flow at runtime) |
| `callingData` | Static | Value: "true" |

Same Static/Dynamic distinction as header parameters.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Configure Request Body (POST/PUT/PATCH Only)

If the method is POST, PUT, or PATCH, configure the request body:

| Field | Value |
|-------|-------|
| **Body format** | JSON (`application/json`), XML (`application/xml`), Text (`text/plain`), or form-data |
| **Parameters** | Add body fields as Static or Dynamic (same pattern as URL/header parameters) |

Skip this section for GET and DELETE methods.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Configure Node Events

Define success/error routing — these become the output ports on the node in the flow canvas:

| Event | Condition |
|-------|-----------|
| **Success** | HTTP Status equals 200 |
| **Error** | HTTP Status not equals 200 |

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Define Response Object

| Field | Value |
|-------|-------|
| **Response Format** | JSON (or Text/XML depending on API) |
| **Parameter name** | Descriptive name (e.g., "Person") |
| **Body** | Body (also supports HTTP Status or HTTP Header) |
| **Response Path** | JSON path to extract (e.g., `$.items[0]` for first array element, `$` for whole response) |

The output is available downstream as the node's variable (e.g., `$(n3.person)` where `n3` is the node number).

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Configure Throttling (Optional)

Protect the target API from overload:

| Field | Value |
|-------|-------|
| **Rate Limit** | Max requests per second |
| **Concurrency Limit** | Max parallel Custom Node executions |
| **Volume Limit** | Max Custom Node executions within a time period |

Set these based on the target API's rate limits.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Configure Node UI (Optional)

Customize how the node's input fields appear in the flow editor:

| Field | Value |
|-------|-------|
| **Information Text** | Description shown in the node config dialog |
| **Field Type** | Text box, Selection box, or Date and time — for each dynamic input |
| **Regex Validation** | Validation string for text inputs (text box only) |
| **Display Name** | Label for selection box options |
| **Value** | Value of selection box options |
| **Date format** | Format of date fields (Date and time only) |
| **Date-Time Separator** | Separator between date and time (Date and time only) |
| **Time format** | Format of time fields (Date and time only) |
| **Mandatory Parameter** | Whether the field is required |
| **Tooltip** | Help text shown on hover |

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Activate the Integration

After saving, the integration is **off by default**. Toggle it ON in the integrations list — otherwise the node won't appear in the flow palette.

### Using the Response

Parse the Custom Node output in an Evaluate node. Set the **Script Output** field to `0`:

```javascript
const person_json = JSON.parse("$(n3.person)");
const person_name = person_json.displayName;
const person_status = person_json.status;
```

### Testing the Custom Node

To validate the Custom Node before wiring it into a production flow:

1. Create a test flow with a **webhook-triggered Start node** (generates a unique webhook URL)
2. Wire: Start → Custom Node → Evaluate (parse response) → End
3. In Postman or curl, **POST an empty JSON body `{}`** to the webhook URL to trigger the flow
4. In Webex Connect, open the flow's **debug logs** (decrypt if needed) and inspect the Custom Node output to confirm the response shape and field extraction

> The callback URL configured in OAuth is not accessible through a web browser. You can only test it by executing the Custom Node in a flow.

[source: [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

### Troubleshooting Custom Node OAuth

| Symptom | Cause | Fix |
|---------|-------|-----|
| Integration shows **"Auth Pending"** or **"re-authorize"** status | Access token and refresh token both expired, OR credentials updated in the integrating system | Navigate to **Assets → Integrations** → select the Custom Node → re-authorize (triggers the OAuth popup flow again) |
| Custom Node returns HTTP 401 at runtime | Access token expired and refresh failed | Same as above — re-authorize. Check that the Refresh URL Token is correct and the refresh token hasn't expired (90-day lifespan for Webex) |
| OAuth popup doesn't appear after clicking Authorize | Browser popup blocker | Allow popups for the Connect domain. Try a different browser if the issue persists |
| OAuth popup shows an error from the provider | Incorrect Consumer ID/Secret, wrong scopes, or redirect URI mismatch | Verify the Consumer ID and Consumer Secret match the Integration at developer.webex.com. Verify the scopes match. Verify the Call Back URL from the Custom Node config is registered as a Redirect URI in the Integration |
| HTTP 429 at runtime | Rate limit exceeded | Reduce request frequency or increase the **Rate Limit** in Throttling config |
| HTTP 430 at runtime | Concurrency limit exceeded | Reduce parallel flow executions or increase the **Concurrency Limit** in Throttling config |
| HTTP 431 at runtime | Volume limit exceeded | Wait for the time window to reset or increase the **Volume Limit** in Throttling config |
| Custom Node not appearing in flow palette | Integration is toggled OFF | Go to **Assets → Integrations** and toggle the integration ON |

> **No proactive token health monitoring:** Cisco does not document email notifications or dashboard indicators for OAuth token expiry on Custom Nodes. Certificate expiry (mTLS) has email alerts at 30/15/7/3/2/1 days before expiry, but OAuth tokens do not. Monitor token health by testing flows periodically or checking the integration status in Assets → Integrations.

[source: [Integrations Troubleshooting](https://help.webexconnect.io/docs/integrations); [Custom Node Integration](https://help.webexconnect.io/docs/custom-nodes)]

> Full walkthrough including Service App and Flow Designer patterns: `docs/playbooks/webex-api-auth.md`

---

## Other Flow Types

This document covers **AI Agent action flows** (Receive node → HTTP Request → Flow Outcomes). Webex Connect also supports other flow patterns documented in separate playbooks:

- **Outbound voice calls** (webhook → Call User → TTS): see `docs/playbooks/outbound-voice.md`
- **Inbound voice calls** (Start node with Inbound Call trigger → Voice Node Group → Play/Collect Input/Call Patch): see `docs/playbooks/inbound-voice.md`
- **Sequential dialing / on-call connect** (Call Patch chaining inside VNG for find-me/follow-me): see `docs/playbooks/sequential-dialing.md`
- **Webhook-triggered flows** (Start node with inbound webhook): see `docs/playbooks/webhook-triggers.md`
- **Webex Calling paging integration** (Connect → paging group via PSTN): see `docs/playbooks/webex-calling-paging.md`

### Voice Outbound Limitations

Webex Connect's Call User node and Voice API v1 dial via PSTN only. They cannot reach Webex Calling internal extensions — only E.164 phone numbers with PSTN routing. If the target endpoint (e.g., a paging adapter, hunt group, or workspace phone) only has a Webex Calling extension and no DID, Connect cannot dial it directly. See `docs/playbooks/dual-call-paging.md` for workarounds using the WxCC Create Task API.
