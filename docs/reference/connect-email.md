# Webex Connect — Email Reference

Email node for outbound email notifications — confirmations, alerts, and rich HTML messages with attachments. Supports AWS SES and SMTP sending routes, HTML templates via Email Composer, and open/click tracking.

**Prerequisite:** This document assumes familiarity with `webex-connect.md` for core flow concepts. For Email as a side-effect in AI agent flows, see also `webex-connect-advanced.md`.

---

## Node Inventory

| Node | Palette Name | Purpose |
|------|-------------|---------|
| **Email** | `Email` | Sends outbound email (text, HTML, or template) |

Single node in the Channels category. No separate "Send Email" node.

---

## Email Node Configuration

### Required Fields

| Field | Required | Details |
|-------|----------|---------|
| **Destination Type** | Yes | `Customer ID` or `Email ID` (direct address) |
| **Destination ID** | Yes | One or more email addresses. Comma-separated for multiple. Accepts variables. |
| **From Email** | Auto | **Disabled field** — auto-populated from the email app asset configuration. Cannot be typed manually. |
| **Subject** | Yes | Subject line with variable support. e.g., `Order Confirmed - $(n3.order_number)` |
| **Email Type** | Yes | `Text` (plain text), `Template` (HTML from Email Composer), or `HTML` (raw HTML content) |
| **Message** | Yes | Body content — plain text, HTML markup, or template selection depending on Email Type |

### Optional Fields

| Field | Details |
|-------|---------|
| **From Name** | Sender display name (e.g., `Acme Services`) |
| **Reply-To Email** | Address where replies go instead of From address |
| **CC** | Comma-separated addresses |
| **BCC** | Comma-separated addresses |
| **Fallback Text** | Plain text fallback when HTML is unsupported (appears for Template/HTML types) |
| **List Unsubscribe URL** | Link to subscription management portal |
| **Unsubscribe Mail-To Address** | Email address for unsubscribe requests |
| **Unsubscribe Email Subject** | Subject line for mail-to unsubscribe |
| **Correlation ID** | Custom tracking identifier |
| **Callback Data** | Additional data for delivery reports (max 2,000 chars) |
| **Notify URL** | Webhook endpoint for delivery status. Toggle "Enable Notify URL Auth" for authenticated callbacks. |

### Tracking Options (AWS SES Only)

| Field | Details |
|-------|---------|
| **Enable Link Tracking** | Tracks link clicks; generates "Clicked" receipt (code 7528) |
| **Track Opens** | Monitors email open events (code 7502). Not available for plain text emails. |

### Attachment Configuration

| Field | Details |
|-------|---------|
| **Static Attachments** | Up to **5 files**, **10 MB total** |
| **MIME Type** | Select from list (PDF, Word, Excel, images, audio, video, ZIP, etc.) |
| **Attachment Name** | Filename as shown to recipient |
| **Media URL** | URL where the file is hosted |
| **Dynamic Attachments** | JSON payload with `attachmentType: 2` (media URL) or `attachmentType: 1` (base64 encoded) |

### Advanced Options

| Setting | Options | Notes |
|---------|---------|-------|
| **Wait For** | `Gateway Submit` or `Delivery Report` | **Always use Gateway Submit in agent flows** |
| **Timeout** | UTC datetime or seconds | Maximum wait when using Delivery Report mode |
| **Expiry** | UTC or seconds | Maximum node execution duration |

### SMTP-Specific Headers

| Field | Details |
|-------|---------|
| **In-Reply-To** | SMTP header for email threading |

---

## Exit Paths

| Event | When | Color |
|-------|------|-------|
| `onSuccess` | Message submitted to gateway (Gateway Submit) or delivered (Delivery Report) | Green |
| `onError` | Internal error during node execution | Red |
| `onInvalidData` | Missing or malformed required data (e.g., no destination) | Red |
| `onPolicyFail` | Policy constraint violated | Red |
| `onTimeout` | Timeout exceeded (Delivery Report mode) | Amber |

---

## Output Variables

| Variable | Description |
|----------|-------------|
| `send.sentDateTime` | Timestamp when message was sent (ISO 8601 UTC) |
| `send.gatewayTid` | Gateway transaction ID |
| `send.deliveryStatusDescription` | Delivery status text |
| `send.deliveryStatusCode` | Numeric status code |
| `send.response_data` | Full gateway response object |

---

## Email Templates

### Template Types

| Type | Description |
|------|-------------|
| **Full Template** | Single complete email (header + body + footer) |
| **Partial Template** | Reusable blocks that combine. Changes to a partial propagate to all emails using it. |

### Creating Templates

1. **Tools > Templates > Add New Template**
2. Name: lowercase letters and underscores only
3. Channel: Email
4. **Reference ID**: used for dynamic template selection in the Email node
5. Choose Full or Partial
6. Subject: max **998 characters**
7. Use the drag-and-drop **Email Composer**: layouts, text blocks, images, buttons, tables, conditional blocks, dividers
8. **Source Mode** available for direct HTML editing

### Using Templates in Flows

When Email Type = Template:
- Select from dropdown (static) or use Reference ID variable (dynamic)
- All replaceable parameters auto-load for variable mapping
- Map each parameter to a flow variable via the variable picker

### Template Limits

| Constraint | Limit |
|-----------|-------|
| Subject line | 998 characters |
| Conditional elements | Max 120 IF/ELSEIF per template |
| Template naming | Lowercase letters and underscores only |

---

## Variable Insertion

Same `$(nX.variableName)` pattern as all Connect nodes:

| Source | Syntax | Example |
|--------|--------|---------|
| Start node (webhook) | `$(n1.inboundWebhook.fieldName)` | `$(n1.inboundWebhook.customer_email)` |
| Receive node (AI Agent) | `$(nX.aiAgent.entityName)` | `$(n2.aiAgent.order_id)` |
| HTTP Request output | `$(nX.outputVar)` | `$(n3.customer_name)` |

For **templates**, replaceable parameters are defined in the template and mapped to flow variables when selected in the Email node.

---

## Wait For Setting

| Mode | Behavior | Agent Flows? | Webhook Flows? |
|------|----------|-------------|----------------|
| **Gateway Submit** | Completes when message enters email gateway queue | **Yes** — fast | Yes — fastest |
| **Delivery Report** | Waits for delivery/bounce confirmation | **No** — will timeout | Yes, if needed |

---

## Sending Routes

### AWS SES

| Feature | Details |
|---------|---------|
| **Setup** | IAM user with `AmazonSESFullAccess`, `AmazonSNSFullAccess`, `AmazonS3FullAccess` |
| **Domain Verification** | Add TXT record to DNS within 24 hours |
| **DKIM** | Add 3 CNAME records; may take up to 72 hours |
| **SPF** | Automatic with default MAIL FROM domain; DNS record needed for custom MAIL FROM |
| **DMARC** | Configure policy record (`p=none`, `p=quarantine`, or `p=reject`) |
| **MX Records** | Required for inbound email capability |
| **Tracking** | Open tracking, click tracking, bounce/complaint notifications |
| **Dedicated IPs** | Recommended ≥2; each limited to 40 TPS; automatic warm-up for new IPs |

### SMTP Route

| Feature | Details |
|---------|---------|
| **Auth** | Username/Password or OAuth 2.0 (recommended) |
| **Port & Security** | Configure port + security type (SSL, STARTTLS, None) |
| **Limitations** | No delivery tracking, no bounce notifications, no open/click tracking |

### Sandbox Note

**Email is NOT available in sandbox/trial accounts.** Requires full platform license.

### SES Sandbox Caveat

SES sandbox accounts must allowlist destination email addresses. Unverified destinations get error **7522**.

---

## Bounce Handling

- Connect **automatically handles bounces** — do NOT enable AWS SES account-level suppression lists
- Hard-bounced addresses suppressed for **7 days** (configurable 1–365 days)
- Suppression applies across **all email assets** in the account
- Code **7240** ("Already Bounced") fires when sending to a previously bounced address within retention
- **SMTP route does not receive bounce notifications**

---

## Unsubscribe Handling

- Enable "Unsubscribe" in email asset configuration
- Adds `List-Unsubscribe` and `List-Unsubscribe-Post` headers to outbound emails
- Unsubscribed addresses automatically filtered from send lists
- **Limitation:** Unsubscribe checking applies only to `To` addresses, NOT `CC` or `BCC`
- Gmail requirement (5,000+ daily): must support one-click unsubscribe
- Custom management: pass `listUnsubscribeUrl`, `unsubscribeEmailAddress`, `unsubscribeEmailSubject`

---

## Size Limits

| Constraint | Limit |
|-----------|-------|
| Total email size (AWS SES) | 10 MB (includes text, HTML, attachments, MIME encoding) |
| MIME encoding overhead | ~137% of original (5 MB attachment → ~6.85 MB after encoding) |
| HTML body (API) | 500 KB |
| Static attachments | Max 5 files, 10 MB total |
| Subject line (templates) | 998 characters |
| Callback data | 2,000 characters |
| Email address length | Local: 64 chars, Domain: 255 chars, Total: 320 chars |
| Max recipients per request (SES) | 50 (combined TO + CC + BCC) |

---

## Delivery Tracking (AWS SES Only)

| Event | Status Code | Available On |
|-------|-------------|-------------|
| Submitted | 7501 | SES + SMTP |
| Delivered | 7500 | SES only |
| Read (opened) | 7502 | SES only |
| Bounce | 7520 | SES only |
| Spam/Complaint | 7521 | SES only |
| Clicked | 7528 | SES only |
| Failed | — | SMTP only |

---

## Status Codes

| Code | Description |
|------|-------------|
| 7500 | Delivered |
| 7501 | Submitted |
| 7502 | Read (opened) |
| 7520 | Bounce (permanent, transient, or undetermined) |
| 7521 | Complaint (spam report) |
| 7522 | Not Verified (SES sandbox — destination not allowlisted) |
| 7523 | Invalid email address format |
| 7524 | Email address exceeds length limits |
| 7528 | Clicked (tracked link) |
| 7535 | Attachment size exceeded |
| 7536 | Template error (unable to fetch or parse) |
| 7240 | Already Bounced (within retention window) |
| 7241 | Unsubscribed (on blocked list) |
| 7553 | SMTP auth failed |
| 7554 | SMTP delivery failure |

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| From Email field disabled / can't type | By design — From address comes from app asset config | Configure sender in Assets > Apps > Email |
| Variable shows literal `$(n3.order_id)` | Typed manually instead of using picker | Always use variable picker |
| Error 7522: "Not verified" | SES sandbox; destination not allowlisted | Allowlist in SES, or move to production |
| Error 7240: "Already bounced" | Previous hard bounce within retention window | Wait for retention to expire (default 7 days) |
| Error 7536: Template parse error | Template not found or invalid syntax | Verify template exists and Reference ID matches |
| Read receipts not generated | Email Type = "Text" (plain text) | Use "HTML" or "Template" for open tracking |
| No delivery/bounce tracking | Using SMTP route | SMTP only tracks Submitted/Failed; switch to SES |
| CC/BCC delivery not trackable | AWS SES limitation | Track `To` recipients only |
| Unsubscribe not working for CC/BCC | Platform checks only `To` addresses | Use individual `To` sends for unsubscribe compliance |
| Emails land in spam | Missing SPF/DKIM/DMARC | Configure all three DNS records; keep spam rate < 0.10% |
| Same sender/recipient ignored | Platform drops emails where From = To | Use different sender and recipient |
| Attachment size error (7535) | Total exceeds 10 MB including MIME encoding (~137%) | Keep raw attachments under 7 MB |
| Max 50 recipients per request | SES limit on combined TO + CC + BCC | Split into multiple sends |

---

## References

- [Email Node](https://help.webexconnect.io/docs/email-node)
- [Email Channel Setup](https://help.webexconnect.io/docs/email)
- [Email Templates](https://help.webexconnect.io/docs/templates-email)
- [Email API (Send Message v2)](https://developers.webexconnect.io/reference/email-api)
- [Email FAQs](https://developers.webexconnect.io/reference/email-faqs)
- [Email Deliverability Best Practices](https://help.webexconnect.io/docs/best-practices-to-improve-email-deliverability)
- [Email Status Codes](https://developers.webexconnect.io/reference/channel-specific-status-codes)
- [Data Streams - Email](https://developers.webexconnect.io/reference/data-streams-email)
