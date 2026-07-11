# Outbound WhatsApp Playbook

## Overview

This playbook covers how to build outbound WhatsApp notifications in Webex Connect — webhook-triggered flows that send a WhatsApp message to a phone number. Two patterns exist: **template messages** (proactive, outside the 24-hour session window) and **session messages** (replies within the 24-hour window). Template messages are the primary pattern for notifications — order confirmations, appointment reminders, shipping updates, payment alerts.

**Key distinction from AI Agent flows:** Outbound WhatsApp flows use the **Start node** (webhook trigger) and **WhatsApp node** — NOT the Receive node / AI Agent Event / Flow Outcomes pattern documented in `connect-flows.md`.

For webhook setup, authentication, and testing: see `webhook-triggers.md`. This playbook assumes the webhook infrastructure is already configured.

---

## 1. Flow Structure

**Prerequisite: Customer Opt-In.** Before building any outbound WhatsApp flow, confirm that explicit customer opt-in is in place. This is a Meta policy requirement — messages sent without opt-in can result in account suspension. See section 6 (Opt-In Requirement) for acceptable methods.

### Template Message (Proactive Notification)

The standard pattern for outbound notifications. Works regardless of whether the customer has messaged recently.

```
Start (Webhook) → [Optional: HTTP Request] → WhatsApp (Template) → End
```

### Session Message (Reply Within 24hr Window)

For replies within an active conversation. All message types are available.

```
Start (Webhook) → [Optional: HTTP Request] → WhatsApp (Text/Media/Interactive) → End
```

### Required Nodes

- **Start node** (always first): webhook trigger receives the external event
- **WhatsApp node**: sends the outbound message (single unified node for all message types)
- **End node**: terminates the flow

### Optional Nodes

- **HTTP Request node** (before WhatsApp): fetch dynamic data from a DB/API before composing the message
- **Branch node** (after WhatsApp): handle different send outcomes (success, error, policy fail)
- **Evaluate node** (before WhatsApp): transform or format variables before inserting into the message

---

## 2. WhatsApp Node Configuration

The **WhatsApp node** lives in the Channels category on the flow palette. Unlike SMS/MMS (two separate nodes), WhatsApp uses a single unified node for all message types. Walk through these fields in order:

### Step 1: Destination

| Field | Value |
|-------|-------|
| **Destination Type** | `WA ID` (phone number with country code) **or** `Customer ID` (primary key of a customer profile for cross-channel communication) |
| **Destination** | E.164 format: `+15551234567`. Use a variable from the webhook payload: `$(n1.inboundWebhook.customer_phone)` |

**Note:** From Number is configured at the asset level, not per-node. There is no From Number dropdown on the WhatsApp node.

### Step 2: Message Type

Select the message type based on your use case:

| Type | Purpose | 24hr Window Required? |
|------|---------|----------------------|
| **Template** | Proactive notifications outside 24hr window | **No** — works anytime |
| **Text** | Replies within 24hr window | Yes |
| **Media** | Rich content (images, documents, videos) within 24hr | Yes |
| **List Messages** | Selection menus within 24hr | Yes |
| **Reply Buttons** | Quick responses (up to 3 buttons) within 24hr | Yes |
| **Location** | Coordinates with optional name/address within 24hr | Yes |
| **Contact** | Contact card within 24hr | Yes |

**For outbound notifications, always use Template.** Templates work regardless of whether the customer has messaged recently.

### Step 3: Template Configuration (If Template Selected)

1. Select an approved template from the dropdown — only templates approved by Meta appear
2. Map **header parameters** if the template header contains variables (text, currency, date-time, image URL, video URL, or document URL)
3. Map **body parameters** using the variable picker — e.g., `$(n3.patient_name)`, `$(n3.appointment_date)`
4. Template must be created and approved **before** building the flow — see section 4

### Step 4: Text/Media Configuration (If Session Message)

**Text messages:**
- Message body, max 4,096 characters
- Formatting: `*bold*`, `_italic_`, `~strikethrough~`, `` `monospace` ``
- **Preview URL** option renders a link preview for the first URL

**Media messages:**
- Select type: Image, Video, Audio, Document, or Sticker
- Provide a publicly accessible URL (no auth-gated or redirecting URLs)
- Optional caption (not available for Audio or Sticker)

**Interactive messages:**
- **List Messages:** configure sections (max 10), rows per section, body text (1,024 chars), optional header/footer
- **Reply Buttons:** configure buttons (max 3), body text (1,024 chars), optional header (text/image/video/document)/footer

### Step 5: Wait For Setting

| Mode | Behavior | Use in Agent Flows? |
|------|----------|---------------------|
| **None** | Exit immediately after send (default) | Yes |
| **Gateway Submit** | Exit on WhatsApp submission acknowledgment | **Yes** — recommended |
| **Delivery Report** | Wait for delivery receipt from recipient device | **No** — will timeout |
| **Read** | Wait until customer reads the message | **No** — will timeout |

**Always use Gateway Submit** in AI agent flows (30-second timeout). Webhook-triggered notification flows can use Delivery Report if you need confirmation before proceeding.

**Caveat:** If the customer has disabled read receipts, Read mode waits until timeout. Use Delivery Report or Gateway Submit for reliability.

### Step 6: Exit Paths

| Event | When |
|-------|------|
| `onSuccess` | Wait For = None; message send executed |
| `onSubmit` | Wait For = Gateway Submit; message submitted to WhatsApp |
| `onDeliveryReportSuccess` | Wait For = Delivery Report; delivery receipt received |
| `onError` | Invalid destination, misconfigured fields, malformed request |
| `onPolicyFail` | Policy checks failed (expiry, contact policy restrictions) |
| `onTimeout` | No acknowledgment received within timeout window |
| `onDeliveryReportFail` | Delivery or read condition not met within timeout |

### Output Variables

| Variable | Description |
|----------|-------------|
| `send.deliveryStatusCode` | Numeric delivery status code |
| `send.deliveryStatusDescription` | Human-readable delivery status |
| `send.sentDateTime` | UTC timestamp of message send |
| `send.gatewayTid` | Unique transaction ID for the message |
| `send.response_interactive` | Whether the customer tapped an interactive button (boolean) |
| `send.response_data` | Customer response data from interactive messages (JSON array) |

See `connect-whatsapp.md` for the full field list, optional fields (Correlation ID, Notify URL, Callback Data, Identity Key Hash), and all message type details.

---

## 3. Variable Insertion

Use Connect's standard `$(nX.variableName)` syntax to insert dynamic values into message bodies and template parameters. **Always use the variable picker** — manually typed variables may arrive empty.

### Variable Sources

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook payload) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.order_id)` |
| HTTP Request node output | `$(nX.outputVar)` | `$(n3.customer_name)` |
| Evaluate script output | `$(nX.outputName)` | `$(n4.formatted_date)` |
| Evaluate custom flow variable | `$(variableName)` — no node prefix | `$(formatted_date)` |

### Template Parameter Syntax

Template parameters use different syntax depending on context:

| Context | Syntax | Example |
|---------|--------|---------|
| Connect flow builder (mapping params) | `$(nX.variableName)` | `$(n3.order_number)` |
| Template creation UI | `$(variable1)` | `$(customer_name)` |
| API calls | `{{1}}`, `{{2}}` (sequential) | `{{1}}` = first parameter |

Do not mix template creation syntax with flow variable syntax.

---

## 4. Template Message Details

### Approval Timeline

Template approval is performed by **Meta**, not Webex Connect. Review times typically range from 24 to 72 hours. Plan ahead — templates must be approved before they can be used in flows.

### Categories

| Category | Use For |
|----------|---------|
| **Marketing** | Promotions, offers, product announcements, upsells |
| **Utility** | Order confirmations, shipping updates, payment reminders, account alerts |
| **Authentication** | One-time passcodes (OTP), verification codes |

**Mixed content rule:** A template combining utility and marketing content is classified as **marketing**.

### Template Components

| Component | Required? | Details |
|-----------|-----------|---------|
| **Header** | No | Text (max 1 variable), Image, Video, or Document |
| **Body** | Yes | Core message text |
| **Footer** | No | Supplementary text |
| **Buttons** | No | CTA (max 2: Visit Website + Call Phone Number) **OR** Quick Reply (max 3). Cannot mix CTA and Quick Reply. |

**Character limit:** Combined header + body + footer + buttons are limited to **1,024 characters** total.

CTA button URLs must be valid HTTPS.

### Creating a Template

1. Navigate to **Tools > Templates** in Webex Connect
2. **Add New Template**: name (lower case letters and underscores only), channel = WhatsApp, select WABA ID
3. Select category and language
4. Configure components — **sample content is mandatory** for any fields containing variables or media
5. **Save** submits the template to Meta/WhatsApp for approval
6. Only **approved** templates appear in the WhatsApp node dropdown

**Important:**
- Template names **cannot be reused** within 30 days of deletion
- Approval is by Meta — review times vary (typically 24-72 hours)

### Common Rejection Reasons

- Variable format errors or missing sample content
- Commerce/business policy violations
- Duplicate content (too similar to existing template)
- Promotional content submitted under utility or authentication categories

### Authentication Templates

- Must use the **WhatsApp preset format** — no custom layouts
- **OTP button required** (copy-code or one-tap style)
- No URLs, media, or emoji allowed in the template
- Parameters limited to **15 characters** maximum

---

## 5. 24-Hour Session Window

| Scenario | Allowed Messages |
|----------|-----------------|
| Customer messaged within 24 hours | **ALL** message types (text, media, interactive, location, contact) |
| Customer messaged >24 hours ago | **Template messages ONLY** |
| Business initiates (no prior customer message) | **Template messages ONLY** |

- The window starts from the customer's **last** inbound message
- Each new customer message resets the 24-hour clock
- Sending a free-form message outside the window returns **error 7710**
- To re-engage: send an approved template message — the customer's reply reopens the window

**For outbound notifications: always use template messages.** They work regardless of window status and are the only reliable pattern for proactive outreach.

---

## 6. Channel Prerequisites

### WhatsApp Business Account

1. Navigate to **Assets > Apps > Configure New App > WhatsApp**
2. Authenticate via Facebook login (Embedded Sign-Up)
3. Select or create a Meta Business Account and WABA (WhatsApp Business Account)
4. Set up business profile (logo, about, address, business category, contact email, business description, website URLs)
5. Choose or add a phone number and display name
6. Verify the number via OTP (SMS or voice call)
7. Complete business verification (optional initially, but **required for scaling** beyond the initial 2,000-message tier)

### Phone Number Requirements

- Must be a valid number with country and area codes — no short codes, no toll-free numbers incapable of receiving OTP
- Supported number types include 10DLC (mobile) and IVR-backed numbers
- Must be owned by the business
- Cannot have an existing WhatsApp personal or business app account registered

### Template Approval

Create templates in **Tools > Templates**, approved by Meta. Only approved templates appear in the WhatsApp node dropdown. Allow 24-72 hours for approval.

### Opt-In Requirement

Explicit customer opt-in is **required** before sending template messages. Acceptable methods: SMS keyword opt-in, website forms, WhatsApp conversation threads (customer initiates), IVR menu selections, physical paper forms.

### Messaging Limits

| Level | Business-Initiated Conversations per 24hr |
|-------|-------------------------------------------|
| **Unverified** | 250 |
| **Verified (2K)** | 2,000 unique customers |
| **Verified (10K)** | 10,000 unique customers |
| **Verified (100K)** | 100,000 unique customers |
| **Unlimited** | No limit |

Customer-initiated conversations are unlimited at all tiers. Levels scale automatically based on message quality and volume history.

**Note (October 2025 change):** Meta now manages messaging limits at the **Business Manager level** — the limit is shared across all phone numbers in the account, not tracked per phone number separately.

### WxCC Registration

After creating the WhatsApp asset: **Assets > Apps > WhatsApp > Manage > Register to Webex Engage**

### Sandbox Limitations

- **10,000 lifetime SMS + WhatsApp requests** (combined across both channels, over the lifetime of the sandbox account — does not reset)
- Up to **5 registered test phone numbers** (must be same country; the primary number cannot be changed after registration, but the 4 secondary numbers can be modified)
- WhatsApp template creation **NOT available** — only pre-provisioned templates
- WhatsApp asset creation **NOT available** — uses pre-provisioned sandbox asset
- From number is auto-populated and cannot be changed

See `connect-whatsapp.md` for complete provisioning details.

---

## 7. Complete Flow Example: Appointment Reminder

```
Start (Webhook: appointment_id, customer_phone)
  |
  v
HTTP Request (GET appointment details from DB by appointment_id)
  |
  v
WhatsApp (Template: appointment_reminder,
          destination: $(n1.inboundWebhook.customer_phone),
          body params: $(n3.patient_name), $(n3.appointment_date), $(n3.doctor_name))
  |
  |--- onSuccess/onSubmit ------→ End
  |--- onError ----------------→ End (or: log error via HTTP Request)
  |--- onPolicyFail -----------→ End
  |--- onTimeout --------------→ End
  |--- onDeliveryReportFail ---→ End
```

### Webhook Payload

```json
{
  "appointment_id": "APT-789",
  "customer_phone": "+15551234567"
}
```

### curl Test

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "key: {your_service_key}" \
  -d '{"appointment_id": "APT-789", "customer_phone": "+15551234567"}' \
  "https://{your-webhook-url}"
```

---

## 8. Known Gotchas

| Issue | Fix |
|-------|-----|
| Template not in dropdown | Not yet approved by Meta — check status in **Tools > Templates** |
| Free-form message rejected with 7710 | 24-hour window expired — send an approved template message instead |
| Template parameter mismatch (7804) | Parameter count doesn't match template definition — verify variable count matches |
| Media URL not loading (7701) | URL not publicly accessible — ensure direct public URL with no auth or redirects |
| Variable arrives empty in message | Typed manually instead of using variable picker. Always use the picker. |
| US marketing messages fail (131049) | Meta paused marketing category templates to US recipients — use utility templates instead |
| Read wait times out | Customer disabled read receipts — use Gateway Submit or Delivery Report mode |
| Template paused (7868/7869) | Low quality rating from too many blocks/reports — improve content or create a new template |
| User opted out (131050) | Customer selected "Stop" or reported the business — respect the opt-out, do not resend |
| Number deactivated by Meta | WhatsApp number inactive too long — send at least 3 SMS per month to maintain activity |
| Location messages won't display in WxCC | Location messages cannot be appended to WxCC conversations — use Google Maps URLs in text/template messages |
| Template edits in WhatsApp Manager don't sync | Changes made in Meta Business Manager bypass Connect — create a new template in Connect instead |

Full gotcha list with causes: see `connect-whatsapp.md`.

---

## References

- [WhatsApp Node](https://help.webexconnect.io/docs/whatsapp-node)
- [WhatsApp Templates](https://help.webexconnect.io/docs/templates-whatsapp)
- [WhatsApp Status Codes](https://developers.webexconnect.io/reference/channel-specific-status-codes)
- [WhatsApp Messaging Limits](https://help.webexconnect.io/docs/whatsapp-messaging-limits)
- [Sandbox WhatsApp](https://help.webexconnect.io/docs/sending-and-receiving-whatsapp-messages-using-sandbox)
- [WhatsApp Asset Creation](https://help.webexconnect.io/docs/whatsapp)
- Complete field reference: `connect-whatsapp.md`
- Webhook setup, authentication, and testing: `webhook-triggers.md`
