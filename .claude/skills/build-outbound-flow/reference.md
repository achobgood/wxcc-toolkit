# Outbound Voice Flow -- Quick Reference

## Flow Structure

```
Start (Webhook) → [HTTP Request (optional)] → Call User → Voice Node Group [ Play (TTS) ] → End
```

## Variable Picker Format

| Context | Format |
|---------|--------|
| Webhook payload field | `$(n1.inboundWebhook.{fieldName})` |
| HTTP node output | `$(nX.{variableName})` |
| Evaluate script output | `$(nX.outputName)` |
| Evaluate custom flow variable | `$(variableName)` — no node prefix |

**NEVER type manually** -- always use the variable picker. Manually typed variables arrive empty at runtime.

## Call User Node

### Required Fields

| Field | Value |
|-------|-------|
| Destination Type | `msisdn` (phone number) or `Customer Id` |
| Destination | E.164 format: `+15551234567`. Use variable picker or hardcode (paging DID). |
| From Number | Select provisioned number, or "Dynamic" + variable |

### Exit Paths

| Event | When |
|-------|------|
| `onAnswer` | Call answered -- enters Voice Node Group |
| `onbusy` | Busy signal |
| `onnoanswer` | Call unanswered |
| `onreject` | Call rejected |
| `onError` | Invalid destination or missing digits |
| `oncallfail` | Network connectivity issue |
| `onPolicyFail` | Callback data > 2KB |
| `onExpiry` | Request expired (only if expiry set) |

## Play Node -- TTS Settings

| Setting | Value |
|---------|-------|
| TTS Processor | Azure (only engine in Connect) |
| Voice Type | Neural (Standard deprecated) |
| Language | Select from list or "Dynamic" (ISO 639) |
| Voice | Azure Neural voice (e.g., `AriaNeural`) or Dynamic |
| Input Format | Plain Text (3,000 chars) or SSML (6,000 chars) |

### Key SSML Tags

| Tag | Purpose |
|-----|---------|
| `<speak>` | Required root wrapper |
| `<say-as interpret-as="characters">` | Spell out: ORD-4521 → "O-R-D-4-5-2-1" |
| `<say-as interpret-as="cardinal">` | Number: 42 → "forty-two" |
| `<say-as interpret-as="ordinal">` | Ordinal: 3 → "third" |
| `<say-as interpret-as="currency">` | Money: $53.21 → "fifty-three dollars..." |
| `<break time="500ms"/>` | Insert pause |
| `<prosody rate="slow">` | Slow down speech |

## Voice Node Group Rules

- Auto-creates when Call User is added
- All voice nodes (Play, Collect Input, IVR Menu) go INSIDE the group
- Non-voice nodes CAN run inside: Evaluate, Branch, HTTP Request, Data Parser, Data Transform, SMS, Email, WhatsApp, Messenger, Apple Messages for Business, Profile, Generate OTP, Validate OTP, Decryption, Encryption
- **Wait for** and **Delay** nodes NOT supported inside
- Max 1,000 groups per flow
- AMD (Answering Machine Detection) configured in group Settings — supports Pre-recorded, Upload File, URL, or TTS audio; AMD TTS has a **2,000-character limit** (different from Play node limits)

## Webhook Config (Start Node)

| Property | Value |
|----------|-------|
| HTTP Method | POST only |
| Content Types | `application/json`, `application/xml` |
| Payload Limit | 256 KB default (error 430 if exceeded) |
| Auth Options | Service key (`key` header), JWT, HMAC signature |

### Response Codes

| Code | Meaning |
|------|---------|
| 1002 | Queued -- request accepted |
| 7000 | Invalid JSON |
| 7001 | Auth failed |
| 7002 | Service key missing |
| 7028 | Invalid signature |
| 430 | Payload too large |

## Paging Group Quick Reference

- DID **required** -- extensions are internal-only, not reachable from PSTN
- **Originator enforcement** -- KEY UNKNOWN: test whether PSTN calls from non-originator trigger the page
- Auto-answer is built into paging group feature (not per-phone setting)
- Up to 75 targets; scale beyond via multicast SIP speakers
- Workarounds if originator blocks: add Connect number as originator, use Dial API, route through Auto Attendant

## Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| TTS reads variable literally | Typed manually instead of picker | Use variable picker |
| `onError` fires immediately | Destination not in E.164 format | Add `+` and country code |
| "Send Voice" node missing | Deprecated in v5.4.x | Use **Call User** node |
| SSML tags read aloud as text | Input Format set to "Plain Text" | Switch to "SSML" |
| Webhook returns 7001 | Service key missing/malformed | Check `key` header |
| Flow doesn't trigger | Flow not published (Made Live) | Click Make Live |
| Variables empty in downstream nodes | Sample input not parsed | Go to Start node, click Parse |
| AMD always detects "machine" | Tuning thresholds undocumented | Test with real numbers |
| AMD TTS prompt truncated or errors | AMD TTS prompt has a 2,000-character limit | Shorten prompt or use Pre-recorded/Upload/URL instead |
| Paging DID doesn't answer | Originator enforcement blocking | Test from external phone first |
| Call connects, no audio | Play node not inside Voice Node Group | Move Play inside the group |
