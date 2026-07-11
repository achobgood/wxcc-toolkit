# Webex Connect — WhatsApp Reference

WhatsApp node for outbound and conversational messaging. WhatsApp is the most-used business messaging channel globally, supporting text, media, templates, interactive messages, location, and contacts. The key concept is the **24-hour session window**: free-form messages of any type are allowed within the window, but only pre-approved template messages can be sent outside it.

**Prerequisite:** This document assumes familiarity with `webex-connect.md` for core flow concepts (variable picker, HTTP nodes, flow structure). For WhatsApp as a side-effect in AI agent flows, see also `webex-connect-advanced.md`.

---

## Node Inventory

Single node in the Connect palette (Channels category):

| Node | Palette Name | Purpose |
|------|-------------|---------|
| **WhatsApp** | `WhatsApp` | All WhatsApp message types — text, media, templates, interactive, location, contacts |

Unlike SMS/MMS (two separate nodes), WhatsApp uses a single unified node for all message types.

---

## WhatsApp Node

### Required Fields

| Field | Required | Details |
|-------|----------|---------|
| **Destination Type** | Yes | `WA ID` (phone number with country code) or `Customer ID` |
| **Destination** | Yes | E.164 format with country code (e.g., `+15551234567`). Accepts variables: `$(nX.variableName)` |
| **Message Type** | Yes | `Text`, `Media`, `Template`, `Location`, `Contact`, `List Messages`, or `Reply Buttons` |

**Note:** From Number is configured at the asset level, not per-node. There is no From Number dropdown on the WhatsApp node.

### Optional Fields

| Field | Details |
|-------|---------|
| **Correlation ID** | Unique ID for delivery report tracking. Accepts variables. |
| **Callback Data** | Additional data sent with delivery reports |
| **Notify URL** | Webhook URL for delivery report callbacks. Enable "Notify URL Auth" checkbox for authentication. |
| **Identity Key Hash** | Authenticates customer identity. Hash mismatch triggers error 7862. |

### Wait For Setting

| Mode | Behavior |
|------|----------|
| **None** | Exit immediately after send (default) |
| **Gateway Submit** | Exit on WhatsApp submission acknowledgment |
| **Delivery Report** | Wait for delivery receipt from recipient device |
| **Read** | Wait until customer reads the message |

**Always use Gateway Submit** in AI agent flows (30-second timeout makes Delivery Report and Read impractical). Webhook-triggered notification flows can use Delivery Report or Read if needed.

**Caveat:** If the customer has disabled read receipts, Read mode waits until timeout. Use Delivery Report or Gateway Submit for reliability.

---

## Message Types

### Text Messages

- Max **4,096 characters**
- Formatting supported: `*bold*`, `_italic_`, `~strikethrough~`, `` `monospace` ``
- **Preview URL** option renders a link preview for the first URL only
- **24-hour window only** — outside the window, use a template

### Media Messages

| Type | MIME Types | Max Size | Caption? |
|------|-----------|----------|----------|
| **Image** | JPEG, PNG | 5 MB | Yes |
| **Video** | MP4, 3GPP (H.264 video + AAC audio) | 16 MB | Yes |
| **Audio** | AAC, AMR, MPEG, OGG (Opus codec only) | 16 MB | No |
| **Document** | PDF, DOC(X), PPT(X), XLS(X), TXT | 100 MB | Yes |
| **Sticker** | WEBP | 100 KB static / 500 KB animated | No |

**Media URL requirements:**
- Must be publicly accessible (no auth-gated URLs)
- Must be a direct URL to the file (no redirects or geo-restrictions)

**Sticker requirements:** 512x512 px, transparent background, under 100 KB for static stickers.

**24-hour window only** — outside the window, media can only be sent as template header components.

### Location Messages

- **Latitude** and **Longitude** required
- **Name** and **Address** optional — address only displays if name is also provided
- **24-hour window only**
- **WxCC caveat:** Location messages cannot be appended to WxCC conversations. Use Google Maps URLs (e.g., `https://maps.google.com/?q=lat,lng`) instead.

### Contact Messages

- **Formatted Name** required
- Optional: Prefix, First/Middle/Last Name, Suffix, Address(es), Email(s), Phone(s), Birthday, Website(s), Organization
- **24-hour window only**

### Interactive: List Messages

| Component | Limit | Required? |
|-----------|-------|-----------|
| **Header Text** | 60 characters | No |
| **Body** | 1,024 characters | Yes |
| **Footer** | 60 characters | No |
| **List Title** (button label) | 24 characters | Yes |
| **Sections** | Max 10 | Yes (min 1) |
| **Rows per Section** | Min 1 | Yes |

Each row contains:
- **Title** — max 24 characters
- **Identifier** — max 200 characters (returned when customer selects this row)
- **Description** — max 72 characters (optional)

**24-hour window only.**

### Interactive: Reply Buttons

| Component | Limit | Required? |
|-----------|-------|-----------|
| **Header** | Text (60 chars), Image, Video, or Document | No |
| **Body** | 1,024 characters | Yes |
| **Footer** | 60 characters | No |
| **Buttons** | Max 3 | Yes (min 1) |

Each button contains:
- **Reply Title** — max 20 characters
- **Identifier** — max 200 characters (returned when customer taps)

**24-hour window only.**

---

## 24-Hour Session Window

| Scenario | Allowed Messages |
|----------|-----------------|
| Customer messaged within 24 hours | **ALL** message types (text, media, interactive, location, contact) |
| Customer messaged >24 hours ago | **Template messages ONLY** |
| Business initiates (no prior customer message) | **Template messages ONLY** |

- The window starts from the customer's **last** inbound message
- Each new customer message resets the 24-hour clock
- Sending a free-form message outside the window returns **error 7710**
- To re-engage: send an approved template message — the customer's reply reopens the window

---

## Template Messages

### Categories

| Category | Use For |
|----------|---------|
| **Marketing** | Promotions, offers, product announcements, upsells |
| **Utility** | Order confirmations, shipping updates, payment reminders, account alerts |
| **Authentication** | One-time passcodes (OTP), verification codes |

**Mixed content rule:** A template combining utility and marketing content is classified as **marketing**.

### Components

| Component | Required? | Details |
|-----------|-----------|---------|
| **Header** | No | Text (max 1 variable), Image, Video, or Document |
| **Body** | Yes | Core message text. Combined header + body + footer + buttons limited to 1,024 characters. |
| **Footer** | No | Supplementary text |
| **Buttons** | No | CTA (max 2: Visit Website + Call Phone) **OR** Quick Reply (max 3). Cannot mix CTA and Quick Reply. |

CTA button URLs must be valid HTTPS.

### Approval Process

1. Navigate to **Tools > Templates** in Webex Connect
2. **Add New Template**: name (lowercase alphanumeric + underscores only), channel = WhatsApp, select WABA ID
3. Select category and language
4. Configure components — **sample content is mandatory** for any fields containing variables or media
5. **Save** submits the template to Meta/WhatsApp for approval
6. Only **approved** templates appear in the WhatsApp node dropdown

**Important:**
- Approval is by **Meta**, not Webex Connect — review times vary
- Template names **cannot be reused** within 30 days of deletion

### Template Parameters

| Context | Syntax | Example |
|---------|--------|---------|
| Connect flow builder | `$(nX.variableName)` | `$(n3.order_number)` |
| Template creation UI | `$(variable1)` | `$(customer_name)` |
| API calls | `{{1}}`, `{{2}}` (sequential) | `{{1}}` = first parameter |

### Authentication Templates

- Must use the **WhatsApp preset format** — no custom layouts
- **OTP button required** (copy-code or one-tap style)
- No URLs, media, or emoji allowed in the template
- Parameters limited to **15 characters** maximum

---

## Exit Paths

| Event | When | Color |
|-------|------|-------|
| `onSuccess` | Wait For = None; message send executed | Green |
| `onSubmit` | Wait For = Gateway Submit; message submitted to WhatsApp | Green |
| `onDeliveryReportSuccess` | Wait For = Delivery Report; delivery receipt received | Green |
| `onTimeout` | No acknowledgment received within timeout window | Amber |
| `onError` | Execution failed — invalid field values, malformed request | Red |
| `onPolicyFail` | Policy checks failed (expiry, contact policy restrictions) | Red |
| `onDeliveryReportFail` | Delivery or read condition not met within timeout | Red |

---

## Output Variables

| Variable | Description |
|----------|-------------|
| `send.deliveryStatusCode` | Numeric delivery status code |
| `send.deliveryStatusDescription` | Human-readable delivery status |
| `send.sentDateTime` | UTC timestamp of message send |
| `send.gatewayTid` | Unique transaction ID for the message |
| `send.response_interactive` | Whether the customer tapped an interactive button (boolean) |
| `send.response_data` | Customer response data from interactive messages (JSON array) |

---

## Variable Insertion

Same `$(nX.variableName)` pattern as all Connect nodes:

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.customer_phone)` |
| Receive node (AI Agent) | `$(nX.aiAgent.entityName)` | `$(n2.aiAgent.phone_number)` |
| HTTP Request output | `$(nX.outputVar)` | `$(n3.order_status)` |
| Evaluate script output | `$(nX.outputName)` | `$(n4.formatted_date)` |
| Evaluate custom flow variable | `$(variableName)` — no node prefix | `$(formatted_date)` |

**Templates** use different syntax: `$(variable1)` in the Connect UI, `{{1}}` in the API. Do not mix with the flow variable `$(nX.variableName)` syntax.

---

## Delivery Receipts

### Status Values

| Status | Code | Meaning |
|--------|------|---------|
| Submitted | 7501 | Message accepted by WhatsApp |
| Delivered | 7500 | Delivered to recipient device |
| Read | 7502 | Message read by recipient |

### Webhook Behavior

- **Retry policy:** 3 attempts, 60 seconds between each
- **Privacy caveat:** Read receipts (7502) may never arrive if the customer has disabled read receipts in WhatsApp settings

---

## Provisioning Prerequisites

### Embedded Sign-Up (Recommended)

1. Navigate to **Assets > Apps > Configure New App > WhatsApp**
2. Authenticate via Facebook login
3. Select or create a Meta Business Account and WABA (WhatsApp Business Account)
4. Set up business profile (logo, description, industry)
5. Choose or add a phone number and display name
6. Verify the number via OTP (SMS or voice call)
7. Complete business verification (optional initially, but **required for scaling** beyond Tier 1)

### Phone Number Requirements

- Must be a valid number with country and area codes — **no short codes**
- Must be owned by the business
- Cannot have an existing WhatsApp personal or business app account registered
- **Landline recommended** — mobile numbers face recycling risks from carriers
- US 10DLC numbers with `+1` prefix are supported

### WxCC Registration

After creating the WhatsApp asset: **Assets > Apps > WhatsApp > Manage > Register to Webex Engage**

### Account Activity

Send at least **3 SMS per month** from the registered number to prevent deactivation by Meta.

### Display Name

Can be changed up to **3 times in the first 30 days**, then you must wait **30 days between changes**.

---

## Messaging Limits

| Tier | Business-Initiated Messages per 24hr |
|------|--------------------------------------|
| **Unverified** | 250 |
| **Tier 1** | 2,000 |
| **Tier 2** | 10,000 |
| **Tier 3** | 100,000 |
| **Unlimited** | No limit |

- **Customer-initiated conversations** are unlimited at all tiers
- Tiers scale automatically based on message quality and volume history
- Business verification is required to advance beyond Tier 1

---

## Sandbox Limitations

| Constraint | Limit |
|-----------|-------|
| Lifetime SMS + WhatsApp requests | 10,000 (combined across both channels, 365-day period) |
| Registered test phone numbers | Up to 5 (must be same country, cannot change after registration) |
| WhatsApp template creation | **NOT available** — only pre-provisioned templates |
| WhatsApp asset creation | **NOT available** — uses pre-provisioned sandbox asset |
| Authentication method | Service Key only (no JWT) |
| From number | Auto-populated (cannot change) |

---

## Opt-In Requirements

Explicit customer opt-in is **required** before sending template messages.

**Acceptable opt-in methods:**
- SMS keyword opt-in
- Website forms or checkboxes
- WhatsApp conversation threads (customer initiates)
- IVR menu selections
- Physical paper forms (signed)

**Each opt-in must include:**
- A visual consent element (checkbox, button, signature)
- Description of the type of communications the customer will receive
- Reference to the WhatsApp phone number or business name
- WhatsApp branding per Meta guidelines

**Error 131050** is returned when sending to a customer who has opted out.

---

## Status Codes

### Success

| Code | Meaning |
|------|---------|
| 7500 | Delivered to recipient device |
| 7501 | Submitted to WhatsApp |
| 7502 | Read by recipient |

### Common Failures — Content & Media

| Code | Meaning |
|------|---------|
| 7701 | Media download error — URL not accessible or timed out |
| 7714 | Message too long (exceeds 4,096 characters) |
| 7861 | Unsupported MIME type for the media file |

### Common Failures — Rate Limiting

| Code | Meaning |
|------|---------|
| 7706 | Rate limit exceeded for this WABA |
| 7711 | Spam limit hit — too many messages flagged |
| 7845 | Throughput exceeded for current messaging tier |

### Common Failures — Templates

| Code | Meaning |
|------|---------|
| 7804 | Template parameter count mismatch — wrong number of variables |
| 7805 | Template missing — not found for this WABA |
| 7808 | Template parameter too long — exceeds character limit |
| 7849 | Template does not exist in WhatsApp |
| 7868 | Template disabled by Meta |
| 7869 | Template paused due to low quality rating |

### Common Failures — Session & Policy

| Code | Meaning |
|------|---------|
| 7710 | Re-engagement message outside 24-hour window — use a template |
| 131049 | Meta paused marketing messages to this region (commonly US) |
| 131050 | User opted out — customer selected "Stop" or reported spam |

### Common Failures — Account & Destination

| Code | Meaning |
|------|---------|
| 7726 | Invalid user — cannot be reached on WhatsApp |
| 7737 | Invalid destination — phone number format error |
| 7803 | WABA account locked by Meta |
| 7865 | Recipient not on WhatsApp |

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Free-form message fails with 7710 | Sent outside the 24-hour session window | Send an approved template message to re-engage; customer reply reopens the window |
| Read wait times out | Customer disabled read receipts in WhatsApp settings | Use Delivery Report or Gateway Submit mode instead of Read |
| Identity hash mismatch (7862) | Customer changed devices or reinstalled WhatsApp | Capture the new identity key hash from the updated device |
| Template rejected by Meta | Variable format errors, policy violations, or missing sample content | Review Meta's rejection reason, fix content, and resubmit |
| Template paused (7868/7869) | Low quality rating — too many blocks or reports from recipients | Improve template content, reduce send frequency, or create a new template |
| US marketing messages fail (131049) | Meta paused marketing category templates to US recipients | Use utility category templates instead; marketing availability varies |
| User opted out (131050) | Customer selected "Stop" or reported the business | Respect the opt-out; do not attempt to resend |
| Number deactivated by Meta | WhatsApp number inactive too long | Send at least 3 SMS per month from the registered number to maintain activity |
| Template edits in WhatsApp Manager don't sync | Changes made in Meta Business Manager bypass Connect | Create a new template in Connect instead of editing in WhatsApp Manager |
| Variable arrives empty in message | Variable path typed manually instead of using picker | Always use the **variable picker** to insert `$(nX.variableName)` values |
| Location messages won't display in WxCC | Location messages cannot be appended to WxCC conversations | Use Google Maps URLs (`https://maps.google.com/?q=lat,lng`) in text or template messages |
| Sticker not rendering | Wrong dimensions, file size, or format | Must be 512x512 px WEBP, transparent background, under 100 KB for static |
| Audio not playing on recipient device | Wrong codec for OGG files | OGG audio files must use the **Opus** codec only — other codecs are rejected |
| Sandbox quota error (7020) | Exceeded the combined 10,000 lifetime SMS + WhatsApp limit | Upgrade to a production account |
| Media URL not loading | URL is not publicly accessible, requires auth, or has geo-restrictions | Ensure the URL is a direct public link with no authentication or redirect |

---

## References

- [WhatsApp Node](https://help.webexconnect.io/docs/whatsapp-node)
- [WhatsApp Templates](https://help.webexconnect.io/docs/templates-whatsapp)
- [WhatsApp Template Messages API](https://developers.webexconnect.io/reference/whatsapp-template-messages)
- [WhatsApp Category Guidelines](https://help.webexconnect.io/docs/whatsapp-category-guidelines)
- [WhatsApp Media Message API](https://developers.webexconnect.io/reference/whatsapp-media-message)
- [WhatsApp List Messages API](https://developers.webexconnect.io/reference/whatsapp-list-messages)
- [WhatsApp Reply Buttons API](https://developers.webexconnect.io/reference/whatsapp-reply-buttons)
- [WhatsApp Outbound Webhooks](https://developers.webexconnect.io/reference/whatsapp-outbound-webhooks)
- [WhatsApp Status Codes](https://developers.webexconnect.io/reference/channel-specific-status-codes)
- [WhatsApp Messaging Limits](https://help.webexconnect.io/docs/whatsapp-messaging-limits)
- [WhatsApp FAQs](https://developers.webexconnect.io/reference/whatsapp-faqs)
- [WhatsApp Asset Creation](https://help.webexconnect.io/docs/whatsapp)
- [WhatsApp Asset Creation for WxCC](https://help.webexconnect.io/docs/wxcc-whatsapp-asset-creation)
- [Sandbox WhatsApp](https://help.webexconnect.io/docs/sending-and-receiving-whatsapp-messages-using-sandbox)
- [Supported File Types](https://help.webexconnect.io/docs/supported-file-types-for-channels)
