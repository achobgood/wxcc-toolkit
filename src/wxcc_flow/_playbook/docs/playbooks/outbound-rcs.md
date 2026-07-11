# Outbound RCS Notification Playbook

## Overview

This playbook covers how to build outbound RCS (Rich Communication Services) notifications in Webex Connect — specifically, webhook-triggered flows that check device capability, send a rich card or text message via RCS, and fall back to SMS when the recipient doesn't support RCS. This is the pattern for order-ready notifications, appointment confirmations, and promotional alerts on Android devices.

**Key distinction from SMS flows:** RCS flows require a **two-node pattern** — an RCS Capability check before the RCS Message node. You cannot blindly send RCS; not every Android device supports it, and no iOS devices do. Always wire an SMS fallback.

**Flow structure:**

```
Start (Webhook)
  → [Optional: HTTP Request]
  → RCS Capability (check recipient)
    → onSuccess → Branch (rcs.enabled == true AND rcs.version == "up2")
      → [Yes] → RCS Message (rich card / text) → End
      → [No]  → SMS (plain text fallback) → End
    → onError → SMS (safe fallback) → End
```

For webhook infrastructure (Start node configuration, payload parsing, authentication, testing), see `webhook-triggers.md`. This playbook focuses on the RCS-specific nodes and the capability-check-then-branch pattern.

---

## 1. RCS Capability Check

The **RCS Capability** node verifies whether the recipient's device can receive RCS messages. This MUST run before every RCS Message node.

### Step-by-Step Configuration

1. Drag an **RCS Capability** node from the Channels palette onto the canvas
2. Wire the Start node (or HTTP Request node) output to this node's input
3. Configure the fields:

| Field | Value |
|-------|-------|
| **Mobile Number** | Variable from webhook payload: `$(n1.inboundWebhook.customer_phone)` — must be E.164 format |
| **Force Refresh** | UI defaults to `true` (real-time, 3–6s latency). Set `false` to use a 7-day cached lookup (near-instant) |
| **Carrier** | Leave blank unless you know the recipient's carrier. Takes an **integer** value (e.g., `302`) — not a string carrier code |

### Output Variables

After this node runs, the following variables are available for branching:

**Core variables:**

| Variable | Description | Example Values |
|----------|-------------|----------------|
| `rcs.enabled` | Device has any RCS support | `true` / `false` |
| `rcs.version` | RCS version level | `up1`, `up2`, `disabled` |
| `rcs.platform` | RCS platform provider | `Google`, `Samsung` |
| `rcs.msisdn` | E.164 formatted number | `+15551234567` |

**Per-feature capability booleans** (check these for specific rich content):

> **Platform typo warning:** The RCS Capability node outputs variable names with inconsistent misspellings in the UI. Do NOT type these manually — always use the **variable picker** after running the node to copy the exact names. Three variables are misspelled:
> - `rcs.capabilties.richcard` (typo: "capabilties", not "capabilities")
> - `rcs.capabilites.richcardCarousel` (typo: "capabilites", not "capabilities")
> - `rcs.capabilites.dialPhoneNumber` (typo: "capabilites", not "capabilities")
> - `rcs.capabilities.openUrl` — correctly spelled

| Variable | Feature |
|----------|---------|
| `rcs.capabilties.richcard` | Standalone rich card |
| `rcs.capabilites.richcardCarousel` | Carousel cards |
| `rcs.capabilites.dialPhoneNumber` | Dial phone action |
| `rcs.capabilities.openUrl` | Open URL action |
| `rcs.capabilities.calendarEvent` | Calendar event action |
| `rcs.capabilities.shareLocation` | Share location |
| `rcs.capabilities.viewLocation` | View location |
| `rcs.capabilities.chat` | Chat |
| `rcs.capabilities.fileTransfer` | File transfer |
| `rcs.capabilities.paymentsV1` | Payments |
| `rcs.capabilities.videoCall` | Video call |
| `rcs.capabilities.revocation` | Message revocation |

### Critical: `enabled` vs `version`

`rcs.enabled` = `true` does NOT guarantee rich features. A device with `rcs.version` = `up1` has basic RCS (text only) — NOT rich cards or carousels. For rich content notifications, branch on `rcs.version` == `up2`.

See `connect-rcs.md` for the full list of capability booleans and output variables.

### Exit Paths

| Event | When |
|-------|------|
| `onSuccess` | Capability check completed — proceed to Branch |
| `onError` | Invalid number, network error, lookup failed — fall back to SMS |

---

## 2. Branch Node for RCS Support

After the Capability check succeeds, add a **Branch** node to route the flow based on the recipient's RCS support level.

### Step-by-Step Configuration

1. Drag a **Branch** node onto the canvas
2. Wire `RCS Capability → onSuccess` to this Branch node
3. Configure Branch condition #1 (the "RCS capable" path):

   | Condition | Operator | Value |
   |-----------|----------|-------|
   | `$(nX.rcs.enabled)` | Equals | `true` |
   | **AND** | | |
   | `$(nX.rcs.version)` | Equals | `up2` |

   Where `nX` is the RCS Capability node number (check your flow's node numbering).

   **For maximum safety with rich cards**, add a third condition: `$(nX.rcs.capabilties.richcard)` Equals `true` (note the typo in `capabilties` — use the variable picker to get the exact name). This confirms the device specifically supports rich card rendering, not just RCS version 2.

4. Label this branch "RCS Supported" (or similar)
5. The **None of the above** exit becomes the SMS fallback path — this catches:
   - `rcs.enabled` = `false` (no RCS at all — likely iOS or older Android)
   - `rcs.version` = `up1` (basic RCS only — cannot render rich cards)
   - `rcs.version` = `disabled`

### Wiring

```
Branch
  → [RCS Supported] → RCS Message node
  → [None of the above] → SMS node (fallback)
```

**Also wire** `RCS Capability → onError` directly to the SMS fallback node. If the capability check itself fails (bad number, network issue), always fall back to SMS.

---

## 3. RCS Message Configuration

The **RCS Message** node sends the outbound notification. For notifications, **Rich Card** is the primary format — it delivers a branded, visually structured message with an image, title, description, and interactive suggestion chips.

### Step-by-Step Configuration

1. Drag an **RCS Message** node from the Channels palette
2. Wire the Branch node's "RCS Supported" exit to this node
3. Configure the required fields:

| Field | Value |
|-------|-------|
| **Destination Type** | `MSISDN` |
| **Destination** | `$(n1.inboundWebhook.customer_phone)` |
| **Message Type** | Select the appropriate type (see below) |

### Message Type: Rich Card (Primary for Notifications)

Rich Card is the recommended format for notifications — it renders as a branded card with an image, title, description, and up to 4 interactive suggestion chips.

| Field | Value / Details |
|-------|-----------------|
| **Card Orientation** | `VERTICAL` (most common for notifications) |
| **Media URL** | Public URL to your image — max 2,048 chars, max 500 KB |
| **Media Height** | `SHORT` (1085×310), `MEDIUM` (1080×720), or `TALL` (pixel dimensions not specified in official docs for standalone rich card) |
| **Title** | Notification headline — max 200 characters |
| **Description** | Notification body — max 2,000 characters |
| **Suggestions** | Up to 4 per card (Reply, Open URL, Dial Phone, etc.) |

**Example: Order-Ready Rich Card**

| Field | Example Value |
|-------|---------------|
| **Title** | `Your order $(n3.order_number) is ready` |
| **Description** | `Pick up at $(n3.location_name). Open today until $(n3.closing_time).` |
| **Media URL** | `https://cdn.example.com/store-photo.jpg` |
| **Suggestion 1** | Type: Open URL, Label: "Get Directions", URL: `$(n3.directions_url)` |
| **Suggestion 2** | Type: Dial Phone, Label: "Call Store", Phone: `$(n3.store_phone)` |
| **Suggestion 3** | Type: Reply, Label: "On my way", Postback: `omw_$(n3.order_number)` |
| **Suggestion 4** | Type: Calendar Event, Label: "Add Pickup", Meeting Title: `Pickup $(n3.order_number)` |

**Suggestion chip labels are limited to 25 characters.** Keep labels concise.

### Message Type: Text

For simpler notifications that don't need visual formatting:

| Field | Value / Details |
|-------|-----------------|
| **Text** | Message content — max 1,024 characters (not confirmed in official docs; use as guidance) |
| **Suggestions** | Up to 11 suggestion chips outside the message (documented in carousel context; may vary for standalone text messages) |

### Message Type: Carousel Card

For multi-item notifications (e.g., "Your 3 items are ready"):

| Field | Value / Details |
|-------|-----------------|
| **Card Width** | `SMALL` or `MEDIUM` |
| **Media Height** | Must match across ALL cards. Recommended resolution: 1080×787 px |
| **Cards** | Min 2, max 10 |
| **Per-card fields** | Same as Rich Card |

### Message Type: File

Sends a file to the recipient. See `connect-rcs.md` for supported file types, size limits, and configuration fields.

### Message Type: Typing Indicator

Displays a typing indicator to the recipient. No content fields required — used to signal that a response is being prepared.

See `connect-rcs.md` for the full field list, limits, and all message type options.

### Exit Paths

| Event | When |
|-------|------|
| `onSuccess` | Message sent successfully — wire to End |
| `onSubmit` | "Wait For: Gateway Submit" condition met — wire to End |
| `onDeliveryReportSuccess` | Delivery confirmed by carrier — wire to End |
| `onError` | Gateway rejection — **recommended:** wire to SMS fallback |
| `onDeliveryReportFail` | Delivery report returned failure — wire to SMS fallback (or log) |
| `onPolicyFail` | Expiry condition not met — wire to SMS fallback (or log) |
| `onTimeout` | Timeout period elapsed — wire to SMS fallback (or log) |

### Output Variables

After the RCS Message node runs, these variables are available (prefixed `send.*`):

| Variable | Description |
|----------|-------------|
| `send.sentDateTime` | Timestamp when the message was sent |
| `send.gatewayTid` | Gateway transaction ID |
| `send.deliveryStatusDescription` | Delivery status description |
| `send.deliveryStatusCode` | Delivery status code |
| `send.response_data` | Raw response data from gateway |
| `send.response_interactive` | Interactive response data (for replies) |

### Wait For Setting

| Mode | Behavior | Use in Agent Flows? |
|------|----------|---------------------|
| **Gateway Submit** | Node exits as soon as message enters gateway queue | **Yes** — fast |
| **Delivery Report** | Waits for carrier delivery confirmation | **No** — will timeout |
| **Read Receipts** | Waits for recipient to open message | **No** — will timeout |

**Always use Gateway Submit** in AI agent flows.

---

## 4. SMS Fallback Path

The SMS fallback fires when the recipient doesn't support RCS or when the capability check fails. Deliver the same notification content as plain text.

### Step-by-Step Configuration

1. Drag an **SMS** node onto the canvas
2. Wire three inputs to this node:
   - Branch node → "None of the above" exit
   - RCS Capability node → `onError` exit
   - (Optional) RCS Message node → `onError` exit
3. Configure the SMS node:

| Field | Value |
|-------|-------|
| **Destination** | `$(n1.inboundWebhook.customer_phone)` |
| **Message** | Plain text version of the notification |

**Example:**
```
Your order $(n3.order_number) is ready for pickup at $(n3.location_name). Directions: $(n3.directions_url)
```

Wire `SMS → onSuccess`, `SMS → onError`, `SMS → onPolicyFail`, and `SMS → onTimeout` to End nodes.

---

## 5. Variable Insertion

Use Connect's standard `$(nX.variableName)` syntax to insert dynamic values.

### Where Variables Work

| Context | Variable Method |
|---------|----------------|
| Text message body | `$(nX.variableName)` — direct substitution |
| Rich Card title | Use the **variable picker** in the flow builder |
| Rich Card description | Use the **variable picker** in the flow builder |
| Suggestion chip labels | Use the **variable picker** in the flow builder |
| SMS fallback text | `$(nX.variableName)` — direct substitution |

### Critical Rule

**API substitutions (`$(nX.variableName)`) apply exclusively to text field content** — NOT to rich card titles, descriptions, or suggestion labels when using the API. In the flow builder, always use the **variable picker** for all fields. Manually typed variable references in card fields may arrive empty.

### Variable Sources

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.order_id)` |
| HTTP Request output | `$(nX.outputVar)` | `$(n3.customer_name)` |
| Capability node output | `$(nX.rcs.enabled)` | `$(n4.rcs.enabled)` |

---

## 6. Channel Prerequisites

### RCS App/Asset Setup

1. Navigate to the RCS app configuration in Webex Connect (official docs reference **Tools > Templates** for RCS setup; the exact path may vary by platform version — confirm with your account manager)
2. Configure brand: Display Name (max 40 chars), Description (max 100 chars), Brand Color (4.5:1 contrast ratio vs white), Logo (224×224 px, JPG or PNG)
3. Add Banner Images (1440×448 px; 1080×1080 px as an alternative size is not confirmed in official docs)
4. Set Privacy Policy URL and Terms of Service URL (both required)
5. Add test phone numbers for validation
6. Submit for carrier approval — production launch requires carrier sign-off via your account manager

### Platform Requirements

- **Android only** — Android 8+ with Android Messages or Samsung Messages. No iOS support.
- Carrier must have RCS enabled in the recipient's region
- **Supported countries:** USA, Canada, UK, France, Germany, Spain, Norway, Sweden, India, Japan, Mexico, Brazil, Jordan (not verified in official docs — confirm current list with your account manager)
- Approval timeline: ~7 days for basic messaging program

### Sandbox Limitations

**RCS is NOT available in the Webex Connect Sandbox** (not explicitly confirmed in official docs — verify with your account manager). Sandbox supports only SMS, Voice, and WhatsApp. You need a full platform license to test RCS.

See `connect-rcs.md` for the full provisioning checklist and brand configuration details.

---

## 7. Complete Flow Example: Order-Ready RCS Notification

```
Start (Webhook: order_id, customer_phone)
  |
  v
HTTP Request (GET order details from DB by order_id)
  |  Output: order_number, location_name, closing_time, directions_url, store_phone
  |
  v
RCS Capability (check $(n1.inboundWebhook.customer_phone), Force Refresh: false)
  |
  |--- onSuccess ---> Branch (rcs.enabled == true AND rcs.version == "up2")
  |                      |
  |                      |--- [RCS Supported] ---> RCS Message (Rich Card)
  |                      |                            Title: "Your order $(n3.order_number) is ready"
  |                      |                            Description: "Pick up at $(n3.location_name)."
  |                      |                            Suggestions: [Get Directions] [Call Store] [On my way]
  |                      |                            |
  |                      |                            |--- onSuccess ---> End
  |                      |                            |--- onError -----> SMS (fallback) ---> End
  |                      |
  |                      |--- [None of the above] ---> SMS (fallback)
  |                                                      "Your order $(n3.order_number) is ready
  |                                                       at $(n3.location_name). Directions:
  |                                                       $(n3.directions_url)"
  |                                                      |
  |                                                      v
  |                                                     End
  |
  |--- onError ------> SMS (fallback) ---> End
```

### Webhook Payload

```json
{
  "order_id": "ORD-4521",
  "customer_phone": "+15551234567"
}
```

For webhook setup, authentication, and testing with curl, see `webhook-triggers.md`.

---

## 8. Known Gotchas

| Issue | Fix |
|-------|-----|
| Rich card renders as plain text on recipient's device | Recipient has `rcs.version` = `up1` (basic RCS only). Branch on `rcs.version` == `up2` or check `rcs.capabilties.richcard` before sending rich content |
| Capability says `enabled` but RCS Message fails | `rcs.enabled` only means basic RCS — does not guarantee rich features. Check individual capability booleans |
| Variables empty in rich card title or suggestion labels | API substitutions only apply to text content. Use the **variable picker** in the flow builder for card fields |
| SMS fallback never fires | No Branch node wired after the Capability check. Must explicitly route "None of the above" to SMS |
| Cannot test — "RCS not available" error | RCS is not available in the Webex Connect Sandbox. Requires a full platform license |
| Carousel cards display misaligned | Media Height values don't match across cards. Set identical Media Height on every card in the carousel |

Full gotcha list and status codes in `connect-rcs.md`.

---

## References

- `connect-rcs.md` — full RCS node reference (all fields, limits, status codes, suggestion types)
- `webhook-triggers.md` — Start node webhook setup, authentication, payload parsing
- [RCS Message Node](https://help.webexconnect.io/docs/rcs-message-node)
- [RCS Capability Node](https://help.webexconnect.io/docs/rcs-capability-node)
- [RCS Channel Overview](https://help.webexconnect.io/docs/rcs)
- [RCS App/Asset Setup](https://help.webexconnect.io/docs/rcs-1)
- [RCS API (Send Message v2)](https://developers.webexconnect.io/reference/rcs-api)
