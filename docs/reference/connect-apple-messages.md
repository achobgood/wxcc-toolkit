# Webex Connect — Apple Messages for Business Reference

Apple Messages for Business delivers rich, interactive messages to iOS users — rich links, list pickers, time pickers, forms, Apple Pay, and OAuth authentication, all rendering natively in the Messages app. The critical constraint: **customers must initiate the conversation first**. You cannot cold-send to a phone number.

**Prerequisite:** This document assumes familiarity with `webex-connect.md` for core flow concepts. For Apple Messages as a side-effect in AI agent flows, see also `webex-connect-advanced.md`.

---

## Node Inventory

| Node | Palette Name | Purpose |
|------|-------------|---------|
| **Apple Messages for Business** | `Apple Messages for Business` | Sends outbound messages within an active customer session |

Single node in the Channels category. Formerly called "Apple Business Chat" — the API channel parameter is still `"AppleBusinessChat"`.

---

## Critical Constraint: Active Session Required

**Businesses CANNOT initiate conversations.** The customer must message your business first. This is an Apple platform policy, not a Webex Connect limitation.

### How Customers Initiate

- Messages button on your website
- In-app Messages button
- QR code scan / NFC tag tap
- Apple Maps business listing
- Spotlight / Siri suggestions
- Wallet passes
- Direct URL: `https://bcrw.apple.com/urn:biz:<business-id>`

### Session Duration

**No time limit.** Unlike WhatsApp (24-hour window), Apple Messages has no session expiry. Once a customer messages you, you can reply hours, days, or weeks later.

### Session Termination

A session ends ONLY when:
1. **Customer deletes the conversation thread** — Apple sends a `CONVERSATIONCLOSED` event. Subsequent sends return **HTTP 410 Gone**.
2. **Customer blocks the business.**

### Re-engagement

If a customer closed the conversation, you **cannot** re-engage them. They must message you again from a valid entry point. They return with the **same opaque user ID**.

### Implications for Multi-Channel Flows

In webhook-triggered notification flows, you MUST handle the case where no active session exists:

```
Start (Webhook)
  → Branch: does customer have active AMB session?
    → YES → Apple Messages for Business node
    → NO  → fallback to SMS / RCS / Voice
```

Maintain a record of active sessions by tracking `abcUserId` values and `CONVERSATIONCLOSED` events.

---

## Node Configuration

### General Fields (All Message Types)

| Field | Required | Details |
|-------|----------|---------|
| **Destination Type** | Yes | `User ID` |
| **Destination** | Yes | Customer's `abcUserId` (opaque ID). Accepts variable: `$(nX.variableName)` |
| **Message Type** | Yes | Text, Text with Attachments, Rich Link, List Picker, Time Picker, Payment, New Authentication, iMessage App, Quick Reply, Form Message |
| **Send typing indicator** | No | Checkbox (available on most types) |
| **Correlation ID** | No | Custom tracking ID |
| **Notify URL** | No | Webhook URL for gateway submission status |
| **Callback Data** | No | Custom data for webhook notifications |

### Wait For Options

| Mode | Behavior | Notes |
|------|----------|-------|
| **None** | Fire and forget | Default |
| **Gateway Submit** | Wait for submission confirmation | Use in agent flows |

**No Delivery Report option** — Apple does not provide delivery/read receipts to MSPs.

### Expiry

| Field | Options |
|-------|---------|
| **Expiry** | `UTC` or `Seconds` |
| **Message Expiry** | Date/time or seconds value |

---

## Message Types

### Text

| Field | Details |
|-------|---------|
| **Message** | Up to **10,000 characters** |
| **Send as App Clip** | Optional — iPhones and iPads only |
| **Smart Link** | Optional — with link validity in minutes |

### Text with Attachments

| Field | Details |
|-------|---------|
| **Message** | Text body |
| **URL** | Attachment URL. Use URL-friendly filenames — avoid special characters like `+` |
| **Max attachment size** | **100 MB** |

### Rich Link

| Field | Details |
|-------|---------|
| **Website URL** | Hyperlink destination |
| **Title** | Max **128 characters** |
| **Image URL** | Publicly accessible direct link |
| **MIME type** | image/png, image/jpeg, video/mp4, etc. |
| **Add Video URL** | Optional checkbox — adds video URL + MIME type fields |
| **Rich Link Previews** | Up to **25 domains** with custom preview images (.jpeg/.jpg/.png, under 5 MB, min 50 px) |

### List Picker

| Field | Details |
|-------|---------|
| **Bubble Style** | Small, Icon, or Large |
| **Title / Subtitle** | Bubble preview text |
| **Sections** | Max **20 sections**, max **20 items per section** |
| **Section Item Style** | Small, Icon, or Large |
| **Allow multiple selection** | Checkbox |
| **Request Identifier** | Correlates response back to this message |
| **Reply Message Style/Title/Subtitle** | Shown after customer selects |

Interactive images capped at **64 KB**.

### Time Picker

| Field | Details |
|-------|---------|
| **Bubble Style** | Small, Icon, or Large |
| **Title / Subtitle** | Bubble preview text |
| **Time Slots** | Max **10** — each with title, identifier, timezone, start date/time, duration (seconds) |
| **Location** | Title, latitude, longitude, radius |
| **Request Identifier** | Correlates response |
| **Reply Message** | Style, title shown after selection |

### Payment (Apple Pay)

| Field | Details |
|-------|---------|
| **Line Items** | Array: Type (dropdown), Label, Amount |
| **Total** | Type, Label, Total Amount |
| **Shipping Methods** | Optional: Label, Amount, Detail, Identifier |
| **Country Code** | ISO (e.g., "US") |
| **Currency Code** | ISO (e.g., "USD") |
| **Billing Fields** | Required field selection |
| **Request Identifier** | Unique payment request ID |

**Prerequisites:** Apple Developer account, Merchant ID, PEM certificate, payment gateway URL in Manage App.

### New Authentication (OAuth 2.0)

| Field | Details |
|-------|---------|
| **Received/Reply Message** | Title, subtitle, image configuration |
| **Scope** | OAuth scope items |
| **Request Identifier** | Correlates auth response |
| **Additional Parameters** | Extra OAuth params |

**Prerequisites:** OAuth endpoints and client ID in Apple Business Register. Client secret in Connect Manage App.

### Quick Reply

| Field | Details |
|-------|---------|
| **Summary Text** | Notification text |
| **Options** | 2 to 5 buttons, each with Identifier + Title. Single-select only. |
| **Request Identifier** | Correlates response |

### Form Message

| Field | Details |
|-------|---------|
| **Form Elements** | Complete JSON object defining multi-page form. Supports: select, picker, date, input fields. |

### iMessage App

| Field | Details |
|-------|---------|
| **Team ID** | Apple Developer Team ID |
| **Ext Bundle ID / App ID / App Name** | Extension identifiers |
| **App Icon / URL** | Icon and app URLs |
| **Use Live Layout** | Toggle |

---

## Exit Paths

| Event | When | Color |
|-------|------|-------|
| `onSuccess` | Message submitted to Apple gateway | Green |
| `onError` | No active session, invalid destination, gateway rejection | Red |
| `onPolicyFail` | Policy violation | Red |
| `onInvalidData` | Missing or invalid required data | Red |

**Important:** `onSuccess` means "submitted to Apple's servers," NOT "delivered to device." Apple does not provide delivery or read receipts to MSPs.

---

## Output Variables

| Variable | Description |
|----------|-------------|
| `send.sentDateTime` | Timestamp (GMT) |
| `send.gatewayTid` | Gateway transaction ID |
| `send.deliveryStatusDescription` | Status description |
| `send.deliveryStatusCode` | Status code |
| `send.response_data` | Gateway response |
| `send.response_interactive` | Interactive response data |

**Message-type-specific:**

| Variable | When |
|----------|------|
| `send.richLink` | Rich Link messages |
| `send.ListPicker` | List Picker messages |
| `send.timePicker` | Time Picker messages |
| `send.quickReplies` | Quick Reply messages |

---

## Variable Insertion

Same `$(nX.variableName)` pattern as all Connect nodes:

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.customer_name)` |
| Receive node (AI Agent) | `$(nX.aiAgent.entityName)` | `$(n2.aiAgent.order_id)` |
| HTTP Request output | `$(nX.outputVar)` | `$(n3.appointment_time)` |

---

## Incoming Event Types

When receiving customer messages or interactive responses:

| Event Type | Description |
|-----------|-------------|
| `MO` | Text messages and attachments |
| `INTERACTIVERESPONSE` | List Picker and Time Picker selections |
| `QuickReplyResponse` | Quick Reply button taps |
| `NewAuthenticationResponse` | OAuth authentication result |
| `FormResponse` | Form submission data |
| `iMessageAppResponse` | iMessage App interactions |
| `TYPINGINDICATOR` | `typing_start` or `typing_end` |
| `CONVERSATIONCLOSED` | Customer deleted the conversation |
| `PaymentResponse` | Apple Pay transaction result |

The `capabilityList` field on incoming messages indicates device support: `AUTH`, `LIST`, `TIME`, `QUICK`, `FORM`, `AUTH2`. Apple Pay and Rich Links are supported on all devices.

---

## Provisioning Prerequisites

### Setup Steps

1. **Apple Business Register** — Register at `register.apple.com`. Create a Messages for Business account.
2. **Select Webex Connect as MSP** — Choose "Webex Connect" (formerly IMImobile) during Apple registration.
3. **Automatic app creation** — Once Apple approves and links, an app is auto-created in Connect under Assets > Apps.
4. **Test connection** — Use Apple's "Test your MSP connection" feature. Workaround: append `&name=YOURAPPNAME` to Client Landing Page URL if invalid.
5. **Apple review** — Contact account manager or support@webexconnect.com to start approval.

### For Apple Pay

Apple Developer account, Merchant ID, PEM certificate (from .p12), payment gateway URL in Manage App.

### For OAuth Authentication

OAuth endpoints + client ID in Apple Business Register. Client secret in Connect Manage App.

### Testing

No dedicated sandbox. Test via:
- Apple's internal test accounts through Business Register
- MSP connection test tool
- Real Apple devices (iOS 11.3+, macOS 10.13.4+)

---

## Supported Devices

| Platform | Minimum Version |
|----------|----------------|
| iOS | 11.3+ |
| macOS | 10.13.4+ (High Sierra) |
| iPadOS | All versions |
| watchOS | Supported (via paired iPhone) |

---

## Platform Policies

| Policy | Details |
|--------|---------|
| **Bot requirement** | Bots/virtual agents allowed ONLY if human agent handoff is available |
| **Blocked industries** | Gaming and gambling |
| **Account inactivity** | Commercial accounts with no activity in 3+ months may be deactivated by Apple |
| **No delivery receipts** | Apple does not provide delivery, read, or click events to MSPs |

---

## Limits Summary

| Constraint | Limit |
|-----------|-------|
| Text message length | 10,000 characters |
| Rich Link title | 128 characters |
| List Picker sections | 20 |
| Items per section | 20 |
| Time Picker time slots | 10 |
| Quick Reply options | 2–5 (single-select) |
| Attachment size | 100 MB |
| Interactive message images | 64 KB |
| Rich Link preview domains | 25 per asset |
| Preview image file types | .jpeg, .jpg, .png only |
| Preview image size | Under 5 MB, min 50 px |

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Cannot send to customer | No active session — customer hasn't messaged first | By design. Provide entry points (website button, QR, Apple Maps). |
| HTTP 410 Gone on send | Customer deleted the conversation | Track `CONVERSATIONCLOSED` events. Remove from active session table. Fallback to SMS. |
| No delivery confirmation | Apple doesn't provide DRs | `onSuccess` = submitted to Apple, not delivered. Accept this. |
| Inactive account deactivated | No activity in 3+ months | Ensure regular message activity on commercial accounts. |
| HTTP 404 on send | "No device registrations" — typically during device upgrade | Retry later; messages not auto-retransmitted. |
| Interactive images too large | Over 64 KB | Compress/resize for List Picker, Time Picker thumbnails. |
| Attachment URL with special chars fails | `+` and special chars in filenames | Use URL-friendly filenames. |
| Bot-only deployment rejected | Apple requires human handoff | Add live agent escalation path. |
| Variable arrives empty | Typed manually | Always use variable picker. |
| `abcUserId` confused with phone number | Opaque ID, not a phone number | Cannot reverse-lookup phone from `abcUserId`. Maintain own mapping. |
| Classical Authentication deprecated | Old OAuth flow | Use "New Authentication" message type. |

---

## Channel Comparison

| Dimension | SMS | RCS | Apple Messages |
|-----------|-----|-----|---------------|
| Initiation | Business can cold-send | Business can cold-send | Customer must initiate |
| Session window | N/A (stateless) | N/A (stateless) | No time limit; ends on delete |
| Delivery receipts | Yes | Yes | No (submission only) |
| Rich messages | No | Yes (cards, carousels) | Yes (rich links, pickers, forms, Pay, Auth) |
| Destination ID | Phone (E.164) | Phone (E.164) | Opaque `abcUserId` |
| Platform | All phones | Android (RCS-enabled) | iOS 11.3+, macOS 10.13.4+ |
| Fallback needed | No | Yes (to SMS) | Yes (to SMS/RCS — may have no session) |

---

## References

- [Apple Messages for Business Node](https://help.webexconnect.io/docs/apple-messages-for-business)
- [Apple Messages Channel Setup](https://help.webexconnect.io/docs/apple-messages-for-business-1)
- [Apple Messages API](https://developers.webexconnect.io/reference/apple-messages-for-business-apis)
- [Apple Messages FAQs](https://developers.webexconnect.io/reference/faqs-apple-messages-for-business)
- [Apple Messages Outbound Webhooks](https://developers.webexconnect.io/reference/abc-outbound-webhooks)
- [Apple Messages Setup Guide](https://help.webexconnect.io/docs/messages-for-business-setup)
- [WxCC Apple Messages Integration](https://help.webexconnect.io/docs/wxcc-apple-messages-for-business)
- [Apple Business Register FAQ](https://register.apple.com/resources/messages/messaging-documentation/faq)
- [Apple MSP API](https://register.apple.com/resources/messages/msp-api-tutorial/receiving-sending-messages)
- [Rich Link API](https://developers.webexconnect.io/reference/apple-message-for-business-rich-link)
- [List Picker API](https://developers.webexconnect.io/reference/apple-message-for-business_-list-picker)
- [Time Picker API](https://developers.webexconnect.io/reference/apple-message-for-business-time-picker)
