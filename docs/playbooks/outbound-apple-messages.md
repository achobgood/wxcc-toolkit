# Outbound Apple Messages for Business Notification Playbook

## Overview

This playbook covers how to build outbound Apple Messages for Business notifications in Webex Connect — specifically, webhook-triggered flows that check for an active customer session, send a rich link or interactive message via Apple Messages, and fall back to SMS when no session exists. This is the pattern for appointment confirmations, order updates, and service alerts on iOS devices.

**Critical constraint: Apple Messages requires an active customer session.** Unlike RCS or SMS, you CANNOT cold-send to a phone number. The customer must have messaged your business first. Every Apple Messages notification flow must check for an active session and wire an SMS fallback for customers who haven't initiated contact.

**Flow structure:**

```
Start (Webhook)
  → [Optional: HTTP Request]
  → Branch (active Apple Messages session?)
    → [Yes] → Apple Messages for Business (Rich Link / List Picker) → End
    →         (wire onError → SMS fallback → End)
    → [No]  → SMS (fallback) → End
```

For webhook infrastructure (Start node configuration, payload parsing, authentication, testing), see `webhook-triggers.md`. This playbook focuses on the session-check pattern, Apple Messages node configuration, and the mandatory SMS fallback.

---

## 1. Session Requirement

Apple Messages for Business enforces a strict policy: **businesses cannot initiate conversations.** The customer must message you first through one of Apple's entry points (website Messages button, QR code, Apple Maps listing, Spotlight, or direct URL).

### Session Lifecycle

| Event | What Happens |
|-------|-------------|
| **Customer messages you** | Session starts. You receive an `abcId` (opaque ID — not a phone number). |
| **You send replies** | Allowed at any time while session is active. **No time limit** (unverified — not confirmed in official Webex Connect docs) — unlike WhatsApp's 24-hour window. |
| **Customer deletes conversation** | Apple sends a `CONVERSATIONCLOSED` event (unverified in official Webex Connect docs). Session ends. Subsequent sends may return **HTTP 410 Gone** (Apple platform behavior — not documented on official Webex Connect help pages). |
| **Customer blocks business** | Session ends. No notification sent. |

### Why This Matters for Notifications

In a webhook-triggered notification flow, you have no guarantee the recipient has an active Apple Messages session. You MUST:

1. Check whether a session exists before attempting to send
2. Always wire an SMS fallback for recipients without an active session
3. Also wire the Apple Messages node's `onError` to SMS — because the session can close between your check and your send

See `connect-apple-messages.md` for the full session lifecycle, entry points, and re-engagement rules.

---

## 2. Session Check Pattern

Since Apple Messages sessions depend on customer-initiated contact, you need a way to know which customers have active sessions. The recommended pattern: maintain a sessions table in your database.

### Session Table Design

Track active sessions with at minimum these fields:

| Field | Purpose |
|-------|---------|
| `customer_id` | Your internal customer identifier |
| `abcId` | The opaque Apple Messages user ID received when they first messaged you (Apple platform identifier: `abcId`) |
| `abc_session_active` | Boolean — `true` when session is open, `false` when closed |
| `customer_phone` | E.164 phone number for SMS fallback |

### Maintaining the Table

- **On inbound message:** Set `abc_session_active` = `true` and store the `abcId`
- **On `CONVERSATIONCLOSED` event:** Set `abc_session_active` = `false` for that `abcId`

### Flow-Level Session Check

In your notification flow, after the Start node:

1. Add an **HTTP Request** node to query your sessions table by `customer_id`
2. The response should include `abc_session_active` and `abcId`
3. Add a **Branch** node to check the session status

### Branch Configuration

| Condition | Operator | Value |
|-----------|----------|-------|
| `$(nX.abc_session_active)` | Equals | `true` |

Where `nX` is the HTTP Request node number.

```
Branch
  → [Active Session] → Apple Messages for Business node
  → [None of the above] → SMS node (fallback)
```

---

## 3. Apple Messages Configuration

The **Apple Messages for Business** node sends the outbound notification within an active session. For notifications, **Rich Link** is the primary format — it renders as a tappable preview card with an image, title, and destination URL.

### Step-by-Step Configuration

1. Drag an **Apple Messages for Business** node from the Node Palette
2. Wire the Branch node's "Active Session" exit to this node
3. Configure the required fields:

| Field | Value |
|-------|-------|
| **Destination Type** | `AbcUser Id` |
| **Destination** | `$(nX.abcId)` — the opaque ID from your sessions table lookup |
| **Message Type** | Select the appropriate type (see below) |

### Message Type: Rich Link (Primary for Notifications)

Rich Link is the recommended format for notifications — it renders as a visually prominent, tappable card with an image preview and title that links to a URL.

| Field | Value / Details |
|-------|-----------------|
| **Website URL** | Destination URL the customer taps to open |
| **Title** | Notification headline — max 128 characters |
| **Image URL** | Publicly accessible direct link to preview image |
| **MIME** | Dropdown — select the image format (e.g., `png`, `jpeg`) |

**Example: Appointment Confirmation Rich Link**

| Field | Example Value |
|-------|---------------|
| **Website URL** | `https://app.example.com/appointments/$(n3.appointment_id)` |
| **Title** | `Your appointment is confirmed for $(n3.appointment_date)` |
| **Image URL** | `https://cdn.example.com/appointment-card.jpg` |
| **MIME** | `jpeg` |

### Message Type: List Picker

For notifications that require the customer to select from options (e.g., "Choose a reschedule time"):

| Field | Value / Details |
|-------|-----------------|
| **Bubble Style** | `Small`, `Icon`, or `Large` |
| **Title** | Bubble preview text (required) |
| **Subtitle** | Bubble preview subtext (required) |
| **Sections** | Max 20 sections, max 20 items per section |
| **Allow multiple selection** | Checkbox |

### Message Type: Time Picker

For appointment scheduling or rescheduling notifications:

| Field | Value / Details |
|-------|-----------------|
| **Bubble Style** | `Small`, `Icon`, or `Large` |
| **Title** | Bubble preview text |
| **Subtitle** | Bubble preview subtext |
| **Time Slots** | Max 10 — each with title, identifier, timezone, start date/time, duration |
| **Location** | Title, latitude, longitude, radius |

See `connect-apple-messages.md` for the full list of message types (Text, Quick Reply, Form, Apple Pay, Authentication, iMessage App).

### Exit Paths

| Event | When |
|-------|------|
| `onSuccess` | Message submitted to Apple gateway — wire to End |
| `onError` | No active session, invalid destination, gateway rejection — wire to SMS fallback |
| `onPolicyFail` | Message blocked by Apple policy — wire to SMS fallback |

### Wait For Setting

Only two modes are available for Apple Messages (Apple does not provide delivery receipts):

| Mode | Behavior |
|------|----------|
| **None** | Fire and forget — node exits immediately |
| **GW submit** | Wait for submission confirmation from Apple's servers |

There is **no Delivery Report option** — Apple does not provide delivery or read receipts to MSPs. `onSuccess` means "submitted to Apple's servers," NOT "delivered to device."

---

## 4. SMS Fallback Path

The SMS fallback is critical for Apple Messages flows — it fires when no active session exists OR when the session closes between your check and your send attempt.

### Step-by-Step Configuration

1. Drag an **SMS** node onto the canvas
2. Wire three inputs to this node:
   - Branch node → "None of the above" exit (no active session)
   - Apple Messages node → `onError` exit (session closed or send failed)
   - Apple Messages node → `onPolicyFail` exit (blocked by Apple policy)
3. Configure the SMS node:

| Field | Value |
|-------|-------|
| **Destination** | `$(n1.inboundWebhook.customer_phone)` |
| **Message** | Plain text version of the notification |

**Example:**
```
Your appointment is confirmed for $(n3.appointment_date) at $(n3.location_name). Details: $(n3.appointment_url)
```

### Why `onError` Must Also Route to SMS

Even if your session check says "active," the customer can delete the conversation at any moment. If they delete it between your Branch check and the Apple Messages send, the node returns `onError` with HTTP 410 Gone. Always wire `onError` to SMS so the customer still gets the notification.

Wire `SMS → onSuccess` and `SMS → onError` to End nodes.

---

## 5. Variable Insertion

Use Connect's standard `$(nX.variableName)` syntax to insert dynamic values into Apple Messages fields.

### Variable Sources

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.appointment_id)` |
| HTTP Request output | `$(nX.outputVar)` | `$(n3.appointment_date)` |
| Session lookup output | `$(nX.abcId)` | `$(n2.abcId)` |

### Where Variables Work

| Context | Variable Method |
|---------|----------------|
| Rich Link title | `$(nX.variableName)` via variable picker |
| Rich Link URL | `$(nX.variableName)` via variable picker |
| Text message body | `$(nX.variableName)` — direct substitution |
| List Picker section items | `$(nX.variableName)` via variable picker |
| SMS fallback text | `$(nX.variableName)` — direct substitution |

Always use the **variable picker** in the flow builder rather than manually typing variable references.

---

## 6. Channel Prerequisites

### Apple Business Register Setup

1. Register at `register.apple.com/business-chat` — create a Messages for Business account
2. Select **IMImobile** (may appear as "Webex Connect" in some regions) as your MSP during registration
3. Once Apple approves and links, an app is auto-created in Connect under **Apps**
4. Test connection using Apple's "Test your MSP connection" feature
5. Contact your account manager to start Apple review

### Platform Requirements

- **Apple devices only** (iOS, macOS, iPadOS, watchOS) — No Android support. Specific minimum OS versions are not documented on official Webex Connect help pages.
- No dedicated sandbox — test via Apple's internal test accounts through Business Register, the MSP connection test tool, or real Apple devices

### Bot Policy

Apple requires that bots/virtual agents provide a **human agent handoff** path. Bot-only deployments will be rejected during Apple review. (Apple platform policy — not documented on official Webex Connect help pages. Apple's own guidelines state escalation must be available at any time during the conversation.)

### Account Activity

Commercial accounts with no message activity in 3+ months may be **deactivated by Apple**. Ensure regular activity on your account.

See `connect-apple-messages.md` for the full provisioning walkthrough, Apple Pay prerequisites, and OAuth setup.

---

## 7. Complete Flow Example: Appointment Confirmation

```
Start (Webhook: appointment_id, customer_id, customer_phone)
  |
  v
HTTP Request (GET appointment details + session status from DB)
  |  Output: appointment_date, location_name, appointment_url,
  |          abc_session_active, abcId
  |
  v
Branch (abc_session_active == true)
  |
  |--- [Active Session] ---> Apple Messages for Business (Rich Link)
  |                            Destination: $(n2.abcId)
  |                            Title: "Appointment confirmed for $(n2.appointment_date)"
  |                            URL: "https://app.example.com/appt/$(n1.inboundWebhook.appointment_id)"
  |                            Image: "https://cdn.example.com/confirmation-card.jpg"
  |                            |
  |                            |--- onSuccess -------> End
  |                            |--- onError --------> SMS (fallback) ---> End
  |                            |--- onPolicyFail ---> SMS (fallback) ---> End
  |
  |--- [None of the above] ---> SMS (fallback)
                                  "Your appointment is confirmed for
                                   $(n2.appointment_date) at $(n2.location_name).
                                   Details: $(n2.appointment_url)"
                                  |
                                  v
                                 End
```

### Webhook Payload

```json
{
  "appointment_id": "APPT-7890",
  "customer_id": "CUST-1234",
  "customer_phone": "+15551234567"
}
```

For webhook setup, authentication, and testing with curl, see `webhook-triggers.md`.

---

## 8. Known Gotchas

| Issue | Fix |
|-------|-----|
| Cannot send to customer — `onError` fires immediately | No active session. Customer hasn't messaged your business first. Provide entry points (website Messages button, QR code, Apple Maps listing) and fall back to SMS |
| HTTP 410 Gone on send | Customer deleted the conversation after your session check but before the send. Track `CONVERSATIONCLOSED` events in your sessions table and always wire `onError` to SMS fallback |
| No delivery confirmation after `onSuccess` | By design. Apple does not provide delivery or read receipts to MSPs. `onSuccess` means submitted to Apple, not delivered to device |
| `abcId` confused with phone number | The Apple Messages user ID is an opaque identifier — it is NOT a phone number. You cannot reverse-lookup a phone from `abcId`. Maintain your own customer-to-session mapping |
| Bot-only deployment rejected by Apple | Apple requires human agent handoff. Add a live agent escalation path to your flow |
| Interactive message images fail to load | Compress/resize thumbnails — a specific size cap is not documented in official Webex Connect docs |

Full gotcha list and status codes in `connect-apple-messages.md`.

---

## References

- `connect-apple-messages.md` — full Apple Messages node reference (all message types, fields, limits, session lifecycle)
- `webhook-triggers.md` — Start node webhook setup, authentication, payload parsing
- [Apple Messages for Business Node](https://help.webexconnect.io/docs/apple-messages-for-business)
- [Apple Messages Channel Setup](https://help.webexconnect.io/docs/apple-messages-for-business-1)
- [Apple Messages API](https://developers.webexconnect.io/reference/apple-messages-for-business-apis)
- [Apple Messages Setup Guide](https://help.webexconnect.io/docs/messages-for-business-setup)
- [Rich Link API](https://developers.webexconnect.io/reference/apple-message-for-business-rich-link)
- [List Picker API](https://developers.webexconnect.io/reference/apple-message-for-business_-list-picker)
- [Time Picker API](https://developers.webexconnect.io/reference/apple-message-for-business-time-picker)
