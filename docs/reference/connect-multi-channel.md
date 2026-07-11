# Webex Connect — Multi-Channel Routing Reference

Patterns for routing notifications across multiple channels (SMS, Email, RCS, Apple Messages, WhatsApp, Voice) within a single Webex Connect flow. Covers the Branch node routing pattern, customer preference lookup, capability checks, fallback chains, and channel selection logic.

**Prerequisite:** This document assumes familiarity with the per-channel reference docs: `connect-sms.md`, `connect-email.md`, `connect-rcs.md`, `connect-apple-messages.md`, `connect-whatsapp.md`. For voice, see `docs/playbooks/outbound-voice.md`.

---

## Multi-Channel Flow Structure

A single webhook triggers one flow. The flow routes to the appropriate channel based on customer preference or device capability.

```
Start (Webhook: customer_id, message, ...)
  → HTTP Request (lookup customer record — get preferred_channel, phone, email, abcUserId)
  → Branch (preferred_channel)
    → "voice"  → Call User → Voice Node Group [Play TTS] → End
    → "sms"    → SMS → End
    → "email"  → Email → End
    → "rcs"    → RCS Capability → Branch (enabled?)
                   → Yes → RCS Message → End
                   → No  → SMS (fallback) → End
    → "apple"  → Branch (has active session?)
                   → Yes → Apple Messages → End
                   → No  → SMS (fallback) → End
    → "whatsapp" → WhatsApp (Template or session) → End
    → default  → SMS (safe fallback) → End
```

---

## Branch Node for Channel Selection

The **Branch node** is the routing engine. Configure it with the customer's preferred channel from a DB lookup.

### Configuration

| Field | Value |
|-------|-------|
| **Input Variable** | `$(nX.preferred_channel)` — from HTTP Request output |
| **Branches** | One per supported channel: `voice`, `sms`, `email`, `rcs`, `apple`, `whatsapp` |
| **Condition** | Equals (case-sensitive) |
| **Default** | "None of the above" → SMS (universal fallback) |

### Variable Source

The `preferred_channel` field comes from the customer's record in your database. Common values:

| Value | Routes To |
|-------|-----------|
| `voice` | Call User node |
| `sms` | SMS node |
| `email` | Email node |
| `rcs` | RCS Capability check → RCS Message (or SMS fallback) |
| `apple` | Active session check → Apple Messages (or SMS fallback) |
| `whatsapp` | WhatsApp node (template or session message, SMS fallback on error) |

If the customer has no preference, the default branch fires → SMS.

---

## Channel-Specific Routing Patterns

### SMS (Direct Send)

Simplest path — no capability check needed. Every phone supports SMS.

```
Branch (sms) → SMS Node → End
```

Configuration: see `connect-sms.md`.

### Email (Direct Send)

No capability check needed if you have the customer's email address.

```
Branch (email) → Email Node → End
```

Configuration: see `connect-email.md`.

### Voice (Direct Call)

```
Branch (voice) → Call User → Voice Node Group [Play TTS] → End
```

Configuration: see `docs/playbooks/outbound-voice.md`.

### RCS (Capability Check + SMS Fallback)

RCS **always** requires a capability check — not every device supports it. This is the most common multi-channel pattern.

```
Branch (rcs)
  → RCS Capability Node (check phone)
    → onSuccess → Branch (rcs.enabled == true AND rcs.version == "up2")
      → [Yes] → RCS Message Node → End
      → [No]  → SMS Node (fallback) → End
    → onError → SMS Node (fallback) → End
```

**Key details:**
- `rcs.enabled` = `true` only means basic RCS. Check `rcs.version` = `up2` for rich cards/carousels.
- Use `Force Refresh: false` for cached lookup (near-instant). `true` adds 3–6s.
- If sending rich content, also check `rcs.capabilities.richcard` = `true`.
- Full configuration: see `connect-rcs.md`.

### Apple Messages (Session Check + Fallback)

Apple Messages requires an **active customer session** — you cannot cold-send. You must maintain a table of active sessions.

```
Branch (apple)
  → Branch (has_active_session == true)
    → [Yes] → Apple Messages Node → End
      → onError → SMS Node (fallback — session may have closed)
    → [No]  → SMS Node (fallback) → End
```

**Key details:**
- The `has_active_session` field must come from YOUR database — Connect does not expose a session check API.
- Track `abcUserId` values from incoming customer messages.
- Remove sessions when you receive `CONVERSATIONCLOSED` events (HTTP 410 Gone).
- Always wire Apple Messages `onError` to a fallback — sessions can close between the check and the send.
- Full configuration: see `connect-apple-messages.md`.

### WhatsApp (Template or Session Message + SMS Fallback)

WhatsApp messages fall into two categories: **template messages** (pre-approved, can be sent anytime) and **session messages** (free-form, only within a 24-hour customer-initiated window). Outside the 24-hour window, you must use a template.

```
Branch (whatsapp)
  → WhatsApp Node (template or session message)
    → onSuccess → End
    → onError → SMS Node (fallback) → End
```

**Key details:**
- **Template messages** require pre-approval by Meta. Use templates for proactive/outbound notifications.
- **Session messages** allow free-form text but only within 24 hours of the customer's last inbound message. Track session windows in your database.
- The customer's phone number must be in E.164 format with an active WhatsApp account.
- Wire `onError` to SMS fallback — the recipient may not have WhatsApp installed, or the template may be rejected.
- Full configuration: see `connect-whatsapp.md`.

---

## Customer Preference Lookup

### Database Schema Pattern

Your customer table needs a `preferred_channel` field:

| Column | Type | Values | Default |
|--------|------|--------|---------|
| `preferred_channel` | text | `voice`, `sms`, `email`, `rcs`, `apple`, `whatsapp` | `sms` |
| `phone` | text | E.164 format | — |
| `email` | text | Email address | — |
| `abc_user_id` | text | Apple Messages opaque ID (nullable) | `null` |
| `abc_session_active` | boolean | Track active Apple sessions | `false` |
| `wa_session_active` | boolean | Track active WhatsApp 24-hour session window | `false` |

### HTTP Request Node

```
GET https://{api-base-url}/customers?id=eq.$(n1.inboundWebhook.customer_id)
```

Output variables to extract:
- `preferred_channel`
- `phone`
- `email`
- `abc_user_id`
- `abc_session_active`

---

## Fallback Chain Strategy

When the preferred channel fails, fall back gracefully:

### Priority-Based Fallback

```
Preferred Channel → Primary Fallback → Ultimate Fallback
─────────────────────────────────────────────────────────
RCS              → SMS              → (done)
Apple Messages   → SMS              → (done)
WhatsApp         → SMS              → (done)
Email            → SMS              → (done)
Voice            → SMS              → (done)
SMS              → (done)           →
```

SMS is always the **ultimate fallback** — every phone supports it.

### Implementation Pattern

Wire each channel's `onError` exit to the SMS fallback:

```
RCS Message → onError → SMS → End
Apple Messages → onError → SMS → End
WhatsApp → onError → SMS → End
Email → onError → SMS → End
Call User → onBusy/onNoAnswer → SMS → End
```

### Cascade Fallback (Advanced)

For high-priority notifications, try multiple channels in sequence:

```
RCS Capability → Branch
  → RCS supported → RCS Message
    → onError → Email
      → onError → SMS → End
  → Not supported → Email
    → onError → SMS → End
```

---

## Wait For Settings by Channel

All channels in a multi-channel flow should use **Gateway Submit** for consistent, fast execution:

| Channel | Wait For | Notes |
|---------|----------|-------|
| SMS | Gateway Submit | Delivery Report blocks for seconds to minutes |
| Email | Gateway Submit | Delivery Report blocks for seconds to minutes |
| RCS | Gateway Submit | Read Receipts available but blocks |
| Apple Messages | Gateway Submit | No Delivery Report option available |
| WhatsApp | Gateway Submit | Delivery Report available but blocks |
| Voice | N/A | Call User node has its own exit paths |

---

## Multi-Channel in AI Agent Flows

When using channels as side-effects within the 30-second agent flow timeout:

```
Receive → HTTP GET → HTTP POST → Branch (preferred_channel)
  → rcs   → RCS Capability → Branch → RCS Message (or SMS) → Flow Outcomes → End
  → email → Email → Flow Outcomes → End
  → sms   → SMS → Flow Outcomes → End
  → apple → Apple Messages → Flow Outcomes → End
  → whatsapp → WhatsApp → Flow Outcomes → End
```

**Timeout warning:** The RCS path (Capability + Branch + RCS/SMS) adds 3 nodes minimum. Combined with HTTP nodes, test that the full flow stays under 30 seconds. Use `Force Refresh: false` on the Capability node.

**Error handling:** Wire every channel's `onError` directly to Flow Outcomes so the agent always gets its data back, even if the notification fails.

---

## Channel Selection Decision Matrix

| Factor | Best Channel |
|--------|-------------|
| Customer has Android with RCS | RCS (rich cards, suggestions, read receipts) |
| Customer has iOS with active session | Apple Messages (rich links, pickers, Apple Pay) |
| Customer has iOS, no session | SMS (can't initiate Apple Messages) |
| Customer uses WhatsApp | WhatsApp (template messages for proactive, session for interactive) |
| Customer has email, prefers written record | Email (HTML with attachments) |
| Urgent, must reach immediately | Voice (phone call) |
| Unknown device / no preference | SMS (universal) |
| High-value notification, wants rich + fallback | RCS → SMS fallback chain |

---

## Provisioning Checklist for Multi-Channel

| Channel | What's Needed | Where to Configure |
|---------|--------------|-------------------|
| SMS | Phone number or Sender ID with SMS feature | Assets > Numbers |
| Email | Email asset (AWS SES or SMTP), domain verification, SPF/DKIM/DMARC | Assets > Apps > Email |
| RCS | RCS app/asset, brand configuration, carrier approval | Assets > Apps > RCS |
| Apple Messages | Apple Business Register enrollment, MSP linkage | register.apple.com + Assets > Apps |
| WhatsApp | WABA (WhatsApp Business Account), phone number verification, message template approval | Meta Business Manager + Assets > Apps > WhatsApp |
| Voice | Voice-enabled phone number | Assets > Numbers (Voice feature) |

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Customer gets both RCS and SMS | RCS Capability check succeeded but message also fell through to SMS fallback | Ensure Branch node routes exclusively — don't wire RCS success AND default to SMS |
| Apple Messages `onError` not caught | Forgot to wire `onError` to fallback | Always wire `onError` on Apple Messages to SMS fallback |
| Preferred channel field is null | Customer record has no preference | Default branch → SMS in the Branch node |
| RCS capability check adds latency | `Force Refresh: true` causes 3–6s live lookup | Use `Force Refresh: false` (7-day cached lookup, near-instant) |
| Multi-channel flow exceeds 30s in agent | Too many nodes in RCS path + HTTP lookups | Simplify: skip capability check in agent flows, use SMS only, or move notification to a separate webhook-triggered flow |
| Apple session check is stale | Session closed between DB check and send | Wire `onError` to SMS fallback; update session status on `CONVERSATIONCLOSED` events |
| Branch conditions case-sensitive | `SMS` ≠ `sms` | Normalize `preferred_channel` values in your database (lowercase) |
| WhatsApp template rejected at runtime | Template not approved or was paused/disabled by Meta | Check template status in Meta Business Manager before going live; monitor for status changes |
| WhatsApp session message sent outside 24-hour window | Customer hasn't messaged in the last 24 hours | Track session windows in your DB; fall back to template messages or SMS outside the window |
| WhatsApp `onError` not caught | Forgot to wire `onError` to fallback | Always wire `onError` on WhatsApp node to SMS fallback — recipient may not have WhatsApp |
| Same message sent to wrong channel | Variable picker wrong node number | Always use variable picker; verify node numbers after adding/removing nodes |

---

## References

- [Branch Node](https://help.webexconnect.io/docs/branch-node) — conditional routing
- [SMS Node](https://help.webexconnect.io/docs/send-sms) — see also `connect-sms.md`
- [Email Node](https://help.webexconnect.io/docs/email-node) — see also `connect-email.md`
- [RCS Capability + Message](https://help.webexconnect.io/docs/rcs-capability-node) — see also `connect-rcs.md`
- [Apple Messages Node](https://help.webexconnect.io/docs/apple-messages-for-business) — see also `connect-apple-messages.md`
- [WhatsApp Node](https://help.webexconnect.io/docs/whatsapp) — see also `connect-whatsapp.md`
- [Call User Node](https://help.webexconnect.io/docs/voice-call-user) — see also `docs/playbooks/outbound-voice.md`
