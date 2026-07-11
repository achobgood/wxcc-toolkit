# Webex Connect — RCS Messaging Reference

RCS (Rich Communication Services) Business Messaging delivers rich, app-like messages to Android devices — rich cards with images, carousels, interactive suggestion chips, and branding. Requires a two-node pattern: check whether the recipient supports RCS, then send the message with an SMS fallback if they don't.

**Prerequisite:** This document assumes familiarity with `webex-connect.md` for core flow concepts (variable picker, HTTP nodes, flow structure).

---

## Node Inventory

Two RCS-specific nodes in the Connect palette:

| Node | Palette Name | Purpose |
|------|-------------|---------|
| **RCS Capability** | `RCS Capability` | Checks if recipient's device supports RCS before sending |
| **RCS Message** | `RCS Message` | Sends outbound RCS messages (text, file, rich card, carousel, typing indicator) |

Both are safe within the 30-second AI agent flow timeout when using Gateway Submit mode and cached capability lookups.

---

## RCS Capability Node

Verifies whether a recipient's device can receive RCS messages. **Always run this before sending RCS** — not every Android device has RCS enabled, and no iOS devices support it.

### Configuration Fields

| Field | Required | Details |
|-------|----------|---------|
| **Mobile Number** | Yes | Phone number in E.164 format or variable: `$(nX.variableName)` |
| **Force Refresh** | No | `false` (default) = 7-day cached lookup (near-instant). `true` = live network check (3–6s latency — avoid in agent flows) |
| **Carrier** | No | Integer carrier code. Leave blank if unknown; improves throughput for single-operator sends |

### Output Variables

**Core variables:**

| Variable | Description | Example Values |
|----------|-------------|----------------|
| `rcs.msisdn` | E.164 formatted number | `+447500661610` |
| `rcs.carrierCode` | Carrier identifier | `CA_ROGERS` |
| `rcs.enabled` | Boolean — device has any RCS support | `true` / `false` |
| `rcs.version` | RCS version level | `up1`, `up2`, `disabled` |
| `rcs.platform` | RCS platform provider | `Google`, `Samsung` |

**Per-feature capability booleans:**

| Variable | Feature |
|----------|---------|
| `rcs.capabilities.richcard` | Standalone rich card |
| `rcs.capabilities.richcardCarousel` | Carousel cards |
| `rcs.capabilities.calendarEvent` | Calendar event action |
| `rcs.capabilities.dialPhoneNumber` | Dial phone action |
| `rcs.capabilities.openUrl` | Open URL action |
| `rcs.capabilities.shareLocation` | Share location action |
| `rcs.capabilities.viewLocation` | View location action |
| `rcs.capabilities.chat` | Chat / text messaging |
| `rcs.capabilities.fileTransfer` | File/media transfer |
| `rcs.capabilities.paymentsV1` | Payments |
| `rcs.capabilities.videoCall` | Video calling |

### Critical: `enabled` vs `version`

`rcs.enabled` = `true` does **not** guarantee rich features. A device with `rcs.version` = `up1` has basic RCS (text only) — NOT rich cards or carousels. Branch on `rcs.version` = `up2` or check individual capability booleans for rich content.

### Exit Paths

| Event | When | Color |
|-------|------|-------|
| `onSuccess` | Capability check completed | Green |
| `onError` | Invalid number, network error, lookup failed | Red |

---

## RCS Message Node

### Required Fields

| Field | Details |
|-------|---------|
| **Destination Type** | `MSISDN` (phone number) or `Customer ID` (profile ID) |
| **Destination** | Phone number in E.164 format or variable: `$(nX.variableName)` |
| **Message Type** | `Text`, `File`, `Rich Card`, `Carousel Card`, or `Typing Indicator` |

### Optional Fields

| Field | Details |
|-------|---------|
| **Carrier** | Integer. Leave blank if unknown |
| **Correlation ID** | User-defined unique ID, returned with delivery reports |
| **Callback Data** | Additional data sent with delivery reports (max 2,000 chars) |
| **Notify URL** | Webhook URL for delivery status notifications |
| **Wait For** | `Gateway Submit`, `Delivery Report`, or `Read Receipts` |
| **Time out** | Seconds duration (used with Wait For) |
| **Expiry** | UTC date/time or seconds |

### Exit Paths

| Event | When | Color |
|-------|------|-------|
| `onSuccess` / `onSubmit` | Message accepted by gateway (Gateway Submit mode) | Green |
| `onDeliveryReportSuccess` | Delivery confirmed (Delivery Report mode) | Green |
| `onError` | Invalid destination, gateway rejection, RCS not supported | Red |
| `onDeliveryReportFail` | Delivery report returned failure | Red |
| `onPolicyFail` | Expiry condition not met | Red |
| `onTimeout` | Timeout period elapsed | Amber |

### Output Variables

| Variable | Description |
|----------|-------------|
| `sendDateTime` | Message send timestamp |
| `gatewayTid` | Gateway transaction ID |
| `deliveryStatusDescription` | Success/failure status text |
| `deliveryStatusCode` | Numeric status code |
| `response_data` | Raw response from gateway |
| `response_interactive` | Interactive response data (postback from suggestions) |

---

## Message Types

### Text

| Field | Limit |
|-------|-------|
| **Text** | Max **1,024 characters** (no 160-char SMS limit) |
| **Suggestions** | Up to **11** suggestion chips outside the message |

### File

| Field | Details |
|-------|---------|
| **Media Content URL** | Publicly accessible direct URL |
| **File Size** | In bytes (must be > 0) |

Supported formats and limits:

| Type | Formats | Max Size |
|------|---------|----------|
| Image | BMP, GIF, JPEG (recommended), PNG | 500 KB |
| Video | MPEG-4 | 500 KB |
| Audio | MP4, M4A, MP3, WAV | 500 KB |
| PDF | PDF (v6.5.0+) | Not documented; may fail on some MaaP providers |

### Rich Card (Standalone)

| Field | Details / Limits |
|-------|-----------------|
| **Card Orientation** | `VERTICAL` or `HORIZONTAL` |
| **Thumbnail Alignment** | `LEFT` or `RIGHT` (horizontal cards only) |
| **Media URL** | Max 2,048 characters; publicly accessible |
| **Media Height** | `SHORT`, `MEDIUM`, or `TALL` |
| **Thumbnail URL** | Max 2,048 chars; max 100 KB (recommended ≤50 KB), 800×800 px square, JPG/PNG |
| **Title** | Max **200 characters** |
| **Description** | Max **2,000 characters** |
| **Suggestions** | Up to **4** per card |

At least one of media, title, or description is required. Total card payload limit: **250 KB**.

Image resolution guidelines:

| Media Height | Recommended Size |
|-------------|-----------------|
| SHORT | 1085 × 310 px |
| MEDIUM | 1080 × 720 px |
| TALL | 1080 × 787 px |

### Carousel Card

| Field | Details / Limits |
|-------|-----------------|
| **Card Width** | `SMALL` or `MEDIUM` |
| **Media Height** | `SHORT`, `MEDIUM`, or `TALL` — **must match across all cards** |
| **Cards** | Min **2**, max **10** |
| **Per-card fields** | Same as Rich Card: Media URL, Thumbnail URL, Title (200 chars), Description (2,000 chars) |
| **Suggestions per card** | Up to **4** in flow builder |
| **Global suggestions** | Up to **11** outside the carousel |

Dynamic carousels: Reference an array variable using JSONPath notation (`$.cars[0].name`). Loops process first-level array nesting only, up to 10 cards max. Incomplete arrays cause loop failure.

### Typing Indicator

Sends a typing notification to the user. No content fields required.

---

## Suggestion Types

Six suggestion types for interactive chips on messages and cards:

| Type | Fields | Description |
|------|--------|-------------|
| **Reply** | `displayText` (max 25 chars), `postbackData` | Pre-configured text reply; tapping sends label text back |
| **Open URL** | `displayText` (max 25 chars), `url` (required), `postbackData` | Opens URL in browser |
| **Dial Phone** | `displayText` (max 25 chars), `phone` (required), `postbackData` | Initiates a phone call |
| **View Location** | `displayText` (max 25 chars), `latitude`, `longitude`, `address`, `postbackData` | Shows location on map |
| **Share Location** | `displayText` (max 25 chars), `postbackData` | Prompts user to share their location |
| **Calendar Event** | `displayText` (max 25 chars), `startTime`, `endTime` (ISO 8601), `meetingTitle` (required), `meetingDescription`, `postbackData` | Creates calendar event |

**Constraints:** Max 25 characters per chip label. Max 4 suggestions per card. Max 11 chip-list suggestions outside the message.

---

## RCS + SMS Fallback Pattern

### Flow-Based (Recommended for Notifications)

```
Start (Webhook)
  → RCS Capability (check $(n1.inboundWebhook.phone))
    → onSuccess → Branch (rcs.enabled == true AND rcs.version == "up2")
      → [Yes] → RCS Message (rich card / text)
      → [No]  → SMS (plain text fallback)
    → onError → SMS (safe fallback)
```

### API-Based (Send Message v2 with Automatic Fallback)

The Send Message API v2 supports automatic SMS fallback via the `options` block:

```json
{
  "channel": "rcs",
  "content": { "type": "text", "text": "Your order is ready." },
  "options": {
    "smsFallback": true,
    "smsSenderId": "your_sms_sender_id",
    "text": "Your order is ready. Reply STOP to opt out."
  }
}
```

Failed RCS messages generate transaction IDs appended with `_fallbackrcs` for tracking.

### GSMA API Fallback (v6.5.0+)

Three parameters: `smsFallback` (boolean), `smsSenderId` (mandatory if enabled), `text` (mandatory if enabled). Requires SMS outbound webhook configured with GSMA FNW.11 API flag enabled.

---

## Delivery Receipts

RCS supports four receipt types:

| Receipt | Status | Code |
|---------|--------|------|
| Submitted | Message entered gateway | `7501` |
| Delivered | Message reached device | `7500` |
| Read | Message opened by recipient | `7502` |
| Failed | Delivery failed | varies |

**RCS advantage over SMS:** Read receipts are available (SMS only provides Submitted and Delivered).

---

## Wait For Setting

| Mode | Behavior | Use in Agent Flows? | Use in Webhook Flows? |
|------|----------|--------------------|-----------------------|
| **Gateway Submit** | Completes when message enters gateway queue | **Yes** — fast, stays under 30s | Yes — fastest |
| **Delivery Report** | Waits for carrier delivery confirmation | **No** — will timeout | Yes, if you need delivery confirmation |
| **Read Receipts** | Waits for recipient to open message | **No** — will timeout | Yes, if you need read confirmation |

**Always use Gateway Submit** in AI agent flows. Webhook-triggered notification flows can use Delivery Report if needed.

---

## Variable Insertion

Same `$(nX.variableName)` pattern as all Connect nodes:

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.customer_phone)` |
| Receive node (AI Agent) | `$(n2.aiAgent.entity_name)` | `$(n2.aiAgent.phone_number)` |
| HTTP Request output | `$(nX.outputVar)` | `$(n3.customer_name)` |
| Capability node output | `$(nX.rcs.enabled)` | `$(n4.rcs.enabled)` |

**Critical:** API substitutions apply **exclusively to text field content** — not to rich card titles, descriptions, or suggestion labels in the API. In the flow builder, use the variable picker for all fields.

---

## Provisioning Prerequisites

### RCS App/Asset Setup

1. **Assets > Apps** in Webex Connect → **Configure New App** → select **RCS**
2. Configure brand:
   - Display Name (max 40 chars, recommended <25)
   - Description (max 100 chars)
   - Brand Color (min 4.5:1 contrast ratio vs white)
   - Logo (224×224 px, <50 KB, JPEG)
   - Banner Images (1440×448 px or 1080×1080 px, JPEG/PNG)
   - Contact Info: up to 3 each of websites, phone numbers, email addresses
   - Privacy Policy URL (required)
   - Terms of Service URL (required)
3. Add test phone numbers for validation
4. Submit for approval — production launch requires carrier sign-off via account manager

### Platform Requirements

- **Android only** — Android 8+ with Android Messages or Samsung Messages. No iOS support.
- Service provider typically **Google** (Google RBM / Jibe platform)
- Carrier must have RCS enabled in the region
- **Supported countries:** USA, Canada, UK, France, Germany, Spain, Norway, Sweden, India, Japan, Mexico, Brazil, Jordan (expanding)
- Approval timeline: ~7 days for basic messaging program

### Sandbox Limitations

**RCS is NOT available in the Webex Connect Sandbox.** Sandbox supports only SMS, Voice, and WhatsApp. Full platform license required for RCS testing.

---

## Status Codes

| Code | Description |
|------|-------------|
| 7500 | **Delivered** |
| 7501 | **Submitted** |
| 7502 | **Read** |
| 7000 | Invalid input (JSON) |
| 7006 | Internal server error |
| 7010 | Service provider exception |
| 7011 | Unknown exception |
| 7301 | Message expired |
| 7307 | Endpoint not reachable |
| 7318 | General bad request |
| 7319 | Not found |
| 7320 | Invalid JSON |
| 7321 | Invalid content (bad field, invalid phone number) |
| 7322 | Provider not configured for chatbot |
| 7323 | Unable to locate carrier for recipient |
| 7324 | Max TPS reached |
| 7325 | Unauthorized access |
| 7326 | Internal system error |
| 7327 | External system error |
| 7328 | Pass-through error detail |
| 7329 | Carrier lookup process failure |
| 7330 | MaaP-specific error |
| 7331 | Rate limited at MaaP, retries expired |
| 7334 | MaaP returned failure IMDN |
| 7740 | Invalid media details |

---

## Limits Summary

| Constraint | Limit |
|-----------|-------|
| Text message length | 1,024 characters |
| Rich card title | 200 characters |
| Rich card description | 2,000 characters |
| Media URL length | 2,048 characters |
| Image/video/audio file size | 500 KB |
| Thumbnail size | 100 KB (≤50 KB recommended) |
| Thumbnail dimensions | 800 × 800 px square |
| Total card payload | 250 KB per card |
| Carousel cards | Min 2, max 10 |
| Suggestions per card | 4 |
| Global suggestions outside message | 11 |
| Suggestion chip label | 25 characters |
| Callback data | 2,000 characters |
| SMS fallback text | 1,024 characters |
| Scheduled message window | Max 7 days ahead |
| Display name | 40 characters (recommended <25) |

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Rich card renders as plain text | Recipient has `rcs.version` = `up1` (basic RCS only) | Branch on `rcs.version` = `up2` or check `rcs.capabilities.richcard` |
| Capability says enabled but message fails | `rcs.enabled` only means basic RCS, not rich features | Check individual capability booleans for specific features |
| Carousel cards misaligned | Media height values don't match across cards | Set identical `Media Height` on every card in the carousel |
| Media fails to load | File > 500 KB, URL not publicly accessible, or `fileSize` set to 0 | Ensure public URL, correct size, and size parameter > 0 |
| Variables empty in suggestion chips | API substitutions only apply to text field content | Use variable picker in flow builder for all fields |
| SMS fallback not firing (API) | Missing required fields | All three required: `smsFallback`, `smsSenderId`, and `text` |
| SMS fallback not firing (flow) | No Branch node after Capability | Wire Branch node to check `rcs.enabled` and route to SMS |
| Cannot test in sandbox | RCS not available in sandbox | Requires full Webex Connect platform license |
| `7322` error | Provider not configured for chatbot | RCS app not set up or not carrier-approved |
| `7323` error | Unable to locate carrier | Number not recognized or carrier not RCS-enabled |
| `7324` / `7331` rate limit errors | Send rate too high | Reduce rate or contact account manager for throughput increase |
| Dynamic carousel fails silently | Incomplete array (nulls) | Ensure arrays are complete with no null entries |
| Brand logo/color not appearing | Wrong dimensions or contrast | Logo: 224×224 JPEG <50 KB. Color: 4.5:1 contrast vs white |

---

## References

- [RCS Message Node](https://help.webexconnect.io/docs/rcs-message-node)
- [RCS Capability Node](https://help.webexconnect.io/docs/rcs-capability-node)
- [RCS Channel Overview](https://help.webexconnect.io/docs/rcs)
- [RCS App/Asset Setup](https://help.webexconnect.io/docs/rcs-1)
- [RCS API (Send Message v2)](https://developers.webexconnect.io/reference/rcs-api)
- [RCS Capability API](https://developers.webexconnect.io/reference/capability-api)
- [RCS FAQs](https://developers.webexconnect.io/reference/rich-communication-services-faqs)
- [RCS Status Codes](https://developers.webexconnect.io/reference/channel-specific-status-codes-1)
- [v6.5.0 Changelog (GSMA SMS Fallback)](https://help.webexconnect.io/changelog/product-update-v650-january-2024)
