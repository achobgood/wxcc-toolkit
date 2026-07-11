# Webex Connect — SMS & MMS Reference

SMS and MMS nodes for outbound text and multimedia messaging. SMS is the universal fallback channel — every phone supports it. Use it for confirmations, alerts, and as the fallback when RCS or Apple Messages are unavailable.

**Prerequisite:** This document assumes familiarity with `webex-connect.md` for core flow concepts (variable picker, HTTP nodes, flow structure). For SMS/MMS as side-effects in AI agent flows, see also `webex-connect-advanced.md`.

---

## Node Inventory

Two separate nodes in the Connect palette (Channels category):

| Node | Palette Name | Purpose |
|------|-------------|---------|
| **SMS** | `SMS` | Text-only messages (GSM-7 or Unicode) |
| **MMS** | `MMS` | Multimedia messages with images, video, audio, documents |

These are distinct nodes — there is no combined "Send SMS" node.

---

## SMS Node

### Required Fields

| Field | Required | Details |
|-------|----------|---------|
| **Destination Type** | Yes | `Customer ID` or `msisdn` (phone number) |
| **Destination** | Yes | E.164 format with country code (e.g., `+15551234567`). Accepts variables: `$(nX.variableName)` |
| **From Number** | Yes | Select from dropdown of provisioned sender IDs, long codes, or short codes |
| **Message Type** | Yes | `Text`, `Flash`, `Binary`, `Unicode`, or `Template` |
| **Message** | Yes | Body text, max **1,024 characters**. Use `\n` for line breaks. Insert variables via picker. |

### Optional Fields

| Field | Details |
|-------|---------|
| **Add SmartLink** | Single URL with multiple offers; includes Link Validity (minutes) |
| **Shortened Links** | Auto-shortens HTTPS links; requires domain selection; Track Clicks option. **Warning:** shortened URL domains may be flagged as spam by carriers. |
| **Correlation ID** | Custom unique ID returned with delivery reports. Accepts variables. |
| **Notify URL** | Webhook URL for delivery report callbacks. Includes "Enable Notify URL Auth" checkbox. |
| **Callback Data** | Additional data sent with delivery reports to the Notify URL |
| **Extra Parameters** | Key-value pairs for additional message attributes |

### Advanced Options

| Setting | Options | Notes |
|---------|---------|-------|
| **Wait For** | `Gateway Submit` or `Delivery Report` | **Always use Gateway Submit in agent flows** |
| **Expiry** | UTC datetime or seconds | Triggers onTimeout if exceeded |

### Message Types

| Type | Purpose | When to Use |
|------|---------|-------------|
| **Text** | Standard GSM-7 encoded SMS | Default for Latin-character messages |
| **Unicode** | UCS-2 encoded | Required for non-Latin characters, emoji. Reduces per-segment limit to 70 chars. |
| **Flash** | Displays immediately on screen, not stored in inbox | Carrier support varies — test before using |
| **Binary** | Raw binary data (WAP push, vCard) | Specialized use cases only |
| **Template** | References a pre-configured template | Variables mapped via `${variable_name}` syntax |

### Exit Paths

| Event | When | Color |
|-------|------|-------|
| `onSuccess` | Message accepted by gateway (Gateway Submit) or delivered (Delivery Report) | Green |
| `onError` | Invalid destination, misconfigured sender, gateway rejection | Red |
| `onPolicyFail` | Contact policy or compliance restrictions block the message | Red |
| `onTimeout` | Expiry threshold exceeded (mainly relevant in Delivery Report mode) | Amber |

### Output Variables

| Variable | Description |
|----------|-------------|
| `sms.transId` | Unique transaction reference ID |
| `sms.destination` | Recipient phone number |
| `sms.deliveryStatus` | Current delivery status |
| `sms.messageCount` | Number of segments (v6.9.0+) |

---

## Character Encoding & Segmentation

### GSM-7 vs UCS-2

| Encoding | Single Message | Concatenated Per-Part | Triggers When |
|----------|---------------|----------------------|---------------|
| **GSM-7** | 160 characters | 153 characters | All characters are in the GSM-7 alphabet |
| **UCS-2** | 70 characters | 67 characters | Any non-GSM-7 character present (emoji, CJK, Arabic, etc.) |

A **single emoji** forces the entire message to UCS-2, cutting capacity by more than half.

### Concatenation Table

| Parts | GSM-7 Total | UCS-2 Total |
|-------|-------------|-------------|
| 1 | 160 | 70 |
| 2 | 306 | 134 |
| 3 | 459 | 201 |
| 4 | 612 | 268 |
| 5 | 765 | 335 |

The Connect SMS node enforces a **1,024-character** field limit regardless of encoding (~7 GSM-7 segments or ~15 UCS-2 segments).

### Extended GSM-7 Characters (2 Characters Each)

These consume **two character positions** in GSM-7:

```
| ^ ~ { } [ ] \
```

A 160-character message containing one of these splits into 2 segments.

---

## MMS Node

### Required Fields

| Field | Required | Details |
|-------|----------|---------|
| **Destination Type** | Yes | `Customer ID` or `msisdn` |
| **Destination** | Yes | E.164 format with country code |
| **From Number** | Yes | Select from dropdown |
| **MMS Subject** | Yes | Up to **80 characters** including Unicode |
| **Media Type** | Yes | Select up to **9 media types** per message |
| **MMS Slide Media URL** | Yes | Publicly accessible URL for each media file |
| **Message** | Yes | Body text, up to **4,096 characters** per slide |

### Optional Fields

| Field | Details |
|-------|---------|
| **Correlation ID** | Custom tracking ID |
| **Notify URL** | Webhook URL with optional auth |
| **Callback Data** | Custom data for delivery reports |

### Advanced Options

| Setting | Options |
|---------|---------|
| **Wait For** | `None`, `Gateway Submit`, `Delivery Report`, `Read` |
| **Expiry** | UTC or Seconds |

### Supported Media Types

| Type | Extensions | Max Size |
|------|-----------|----------|
| Image | .jpg, .png, .gif | 750 KB |
| Audio | .mp3 | 750 KB |
| Video | .mp4 | 750 KB |
| PDF | .pdf | 750 KB |
| Calendar | .ics, .ical | 750 KB |
| Contact | .vcf, .vcard | 750 KB |
| Excel | .xlsx, .xls | 750 KB |

**Overall MMS payload limit: 750 KB** (including headers). Some carriers outside US/Canada limit to **250 KB**.

### Slide Composition Rules

- Max **9 slides** per MMS submission
- **No duplicate MIME types** in the same slide
- Image slides: can include audio, cannot include video
- Video slides: can only include text
- vCard/iCal/PDF slides: cannot mix with audio/video/image
- Video auto-reduces quality to fit; if still too large, falls back to SMS with link

### MMS Exit Paths

| Event | When |
|-------|------|
| `onSuccess` | Message accepted by gateway |
| `onError` | Invalid destination, media URL unreachable, gateway rejection |
| `onDeliveryReportFail` | Timeout during Delivery Report wait |
| `onTimeout` | Expiry threshold exceeded |

---

## Variable Insertion

Same `$(nX.variableName)` pattern as all Connect nodes:

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.customer_phone)` |
| Receive node (AI Agent) | `$(nX.aiAgent.entityName)` | `$(n2.aiAgent.phone_number)` |
| HTTP Request output | `$(nX.outputVar)` | `$(n3.confirmation_number)` |
| Evaluate script output | `$(nX.outputName)` | `$(n4.formatted_date)` |
| Evaluate custom flow variable | `$(variableName)` — no node prefix | `$(formatted_date)` |

**Templates** use different syntax: `${replacement_parameter}` (curly braces, not parentheses).

---

## Wait For Setting

| Mode | Behavior | Agent Flows? | Webhook Flows? |
|------|----------|-------------|----------------|
| **Gateway Submit** | Completes when message enters gateway queue | **Yes** — fast | Yes — fastest |
| **Delivery Report** | Waits for carrier delivery confirmation | **No** — will timeout | Yes, if needed |

**Always use Gateway Submit** in AI agent flows.

---

## Sender ID Types

| Type | Format | Two-Way? | Throughput | Use Case |
|------|--------|----------|------------|----------|
| **Long Code (10DLC)** | 10-digit local number | Yes | Lower (regulated) | Low-to-medium volume business messaging |
| **Short Code** | 5–7 digits | Yes (keywords) | High | High-volume campaigns, notifications |
| **Toll-Free** | +1-8XX format | Yes | Medium | Customer support, transactional |
| **Alphanumeric Sender ID** | 3–11 chars (e.g., "ACME") | **No** (one-way) | Varies | Brand recognition in supported countries |

### US A2P 10DLC Registration

US carriers require 10DLC registration for application-to-person SMS on long codes:

1. Purchase a US landline number with SMS feature enabled
2. Register **Brand** (business identity) with The Campaign Registry (TCR)
3. Register **Campaign** (use case) linked to the brand
4. In Connect: **Assets > Numbers** > select number > **Actions > Request 10DLC** > assign Brand ID and Campaign ID
5. Status badge shows "10DLC Requested" → "10DLC" when approved

**Non-compliance (code 7281):** Messages from unregistered 10DLC numbers are rejected by US carriers.

### India DLT Registration

Numbers for SMS in India must be registered on the DLT portal. Provide Entity ID and `dltTemplateId` with each API call.

---

## SMS Templates

Templates use `${variable_name}` syntax (curly braces). When Message Type = Template:

- Select a pre-configured template from the dropdown
- All template variables must be mapped to flow values
- Templates configured at **Tools > Templates > SMS**
- India DLT: templates must carry a matching `dltTemplateId`

---

## Opt-Out / STOP Keyword Handling

### Contact Policy

Webex Connect has a **Contact Policy** app for consent management with Consent Groups and frequency caps.

**Critical:** Contact Policy does **NOT** auto-enforce on Send nodes. You must add an explicit Contact Policy check in your flow before the SMS node and branch on consent status.

### STOP Keyword

- Configure keyword management at **Assets > Numbers > Keywords**
- Recommended STOP confirmation: `"[Brand] We're sorry to see you go! You will receive no further messages. Reply HELP for help."`
- US carriers require STOP/HELP keyword support — failure to honor opt-outs can result in carrier-level blocking

---

## Delivery Reports

### In Flows

- **Gateway Submit**: node exits immediately on `onSuccess`. No delivery confirmation.
- **Delivery Report**: node blocks until carrier confirms. Can take seconds to minutes.
- **Notify URL**: Configure webhook on the SMS node. DLRs posted asynchronously regardless of Wait For mode.

### Status Values

| Status | Code | Meaning |
|--------|------|---------|
| Submitted | 7501 | Submitted to network, awaiting delivery |
| Delivered | 7500 | Confirmed delivered to handset |
| Failed | varies | Delivery failed at gateway level |
| Un-Delivered | varies | Routed to operator but rejected or expired |
| Clicked | — | Recipient clicked tracked link (API v2 only) |

---

## Provisioning Prerequisites

### Number Provisioning

1. **Assets > Numbers > Get Numbers**
2. Select Phone Number, Short Code, or Sender ID
3. For phone numbers: select country, number type, ensure SMS feature is checked
4. For short codes: choose country, preferred series, volume estimate
5. For sender IDs: choose country, describe use case — operations responds within 3 business days

### Sandbox Limitations

| Constraint | Limit |
|-----------|-------|
| Lifetime SMS + WhatsApp requests | 10,000 (combined) |
| Registered test phone numbers | Up to 5 (same country, cannot change) |
| Two-way SMS | 18 countries |
| One-way SMS | 70+ countries |
| From number | Auto-populated, cannot change |

---

## Status Codes

### Success

| Code | Meaning |
|------|---------|
| 7500 | Delivered to handset |
| 7501 | Submitted to network |

### Common Failures

| Code | Meaning |
|------|---------|
| 7004 | Invalid parameters/values |
| 7101 | Invalid Sender ID (not authorized for destination operator) |
| 7102 | Invalid address (phone number) |
| 7107 | Message length exceeded 1,024 characters |
| 7109 | User on Do Not Disturb list |
| 7111 | Spam content detected by carrier |
| 7201 | Rejected by operator |
| 7203 | Unknown subscriber (invalid number) |
| 7206 | Subscriber SIM full |
| 7207 | Out of coverage area |
| 7208 | Message expired (TTL exceeded) |
| 7209 | Unable to deliver multipart message |
| 7281 | **10DLC campaign error** — sender not registered |
| 7282 | Invalid route — unsupported operator or landline |
| 7302 | Rate limit exceeded |
| 7720 | Recipient blocked messages from sender |

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Message arrives garbled as `?????` | Unicode characters sent with Message Type = "Text" | Set Message Type to "Unicode" |
| Single emoji doubles segment count | One emoji forces UCS-2 encoding (70 chars/segment) | Remove emoji or budget for 2x segments |
| Extended GSM chars (`{ } [ ] \| ~ ^`) eat 2 chars each | Escape sequences in GSM-7 | Count them as 2 when estimating length |
| 7281 Campaign error in US | 10DLC brand/campaign not registered | Register brand + campaign with TCR, assign to number |
| Delivery Report mode times out in agent flow | Carrier DLR can take minutes | **Always use Gateway Submit** in agent flows |
| Contact Policy not blocking opted-out users | Policy does not auto-enforce on Send nodes | Add explicit consent check before SMS node |
| Shortened URLs blocked by carrier | Some carriers flag shortened domains as spam | Test with target carriers; consider full URLs |
| Variable arrives empty | Typed manually instead of using picker | Always use the variable picker |
| From number rejected in destination country | Sender ID not supported/registered in that country | Use locally provisioned number or registered Sender ID |
| MMS media not rendering | URL not publicly accessible, or file exceeds 750 KB | Ensure public URL; compress under 750 KB |
| MMS falls back to SMS with link | Video too large after compression | Reduce video length/quality before upload |
| Flash SMS not received | Not all carriers/devices support it | Use standard Text type for reliability |

---

## References

- [SMS Node](https://help.webexconnect.io/docs/send-sms)
- [MMS Node](https://help.webexconnect.io/docs/mms-node)
- [SMS Length and Encoding](https://developers.webexconnect.io/reference/sms-length-and-encoding-copy1)
- [Character Sets Supported](https://help.webexconnect.io/docs/character-sets-supported-for-messaging)
- [Send SMS API v1](https://developers.webexconnect.io/reference/send-sms-api-v1)
- [Send Message API v2 (SMS)](https://developers.webexconnect.io/reference/send-sms-message-api-v2)
- [SMS FAQs](https://developers.webexconnect.io/reference/sms-faqs)
- [MMS API](https://developers.webexconnect.io/reference/mms-api)
- [Supported File Types](https://help.webexconnect.io/docs/supported-file-types-for-channels)
- [SMS Status Codes](https://developers.webexconnect.io/reference/channel-specific-status-codes-1)
- [Sender ID](https://help.webexconnect.io/docs/sender-id)
- [Short Codes](https://help.webexconnect.io/docs/shortcodes)
- [10DLC Number Assignment](https://help.webexconnect.io/docs/assigning-number-10dlc)
- [Contact Policy](https://help.webexconnect.io/docs/contact-policy)
- [Sandbox SMS](https://help.webexconnect.io/docs/sending-and-receiving-sms-using-sandbox)
- [SMS Templates](https://help.webexconnect.io/docs/templates)
