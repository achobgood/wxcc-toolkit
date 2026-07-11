## Bridged Transfer Activity

Temporarily transfers a call to an external destination while **retaining flow control**. When the third party hangs up (or on failure), the call returns to the flow for further handling.

**Dequeue enhancement:** Bridged Transfer is enhanced to dequeue the contact when sending a contact to a third-party interactive voice response (IVR) or automatic call distribution (ACD). If the contact is not handled in the third-party system, it can be taken back to the original queue. For example, a contact center with both Webex Contact Center agents and agents on an external call center/PBX can queue a call against Webex Contact Center agents for a brief period (say 60 seconds). If no agent is available during that period, the call can be bridge transferred (with an implicit dequeue) to the external call center for handling to improve the response time.

### Configuration

| Field | Description |
|---|---|
| Activity Label | Name for the activity |
| Transfer Dial Number | Specific number or `{{variable}}` — the destination DN |
| Timeout | 1–120 seconds (default 10) — how long to wait for answer |
| Send Output Digits | Optional DTMF outpulsing after answer (up to 32 chars: 0-9, A-D, *, #, comma for 1s delay) |
| Add Header | Optional SIP X-Headers (up to 20, LGW only) |

**SIP header PII warning:** Do not include the following sensitive PII in SIP headers:

- Full names of individuals
- Social Security Numbers (any part)
- Physical addresses (home or work)
- Financial information (credit card numbers, bank account details)
- Health information (health-related details or data that could be considered PHI)

**Reserved SIP header patterns (Bridged Transfer):** The following 11 header patterns are reserved for internal use and must not be passed as custom headers. Any headers matching these patterns are dropped and not passed to Webex Contact Center:

- `X-BroadWorks-Correlation-Info`
- `X-FS-Support`
- `X-Path`
- `X-RTMS-CID`
- `X-RTMS-OID`
- `X-RTMS-CONFID`
- `X-RTMS-AGENT-LEGID`
- `X-RTMS-ENTER-SOUND`
- `X-RTMS-APP-PREFIX`
- `X-RTMS-No-Lookup`
- `X-VPOP-DOMAIN`

### Output Paths

**Non-terminal node.** The call returns to the flow after the third party hangs up or on failure. Wire one output edge and branch on `FailureCode`.

### Output Variables

| Variable | Description |
|---|---|
| `BridgedTransfer_dxm.FailureCode` | Error/status code (0 = success) |
| `BridgedTransfer_dxm.FailureDescription` | Human-readable failure description |
| `BridgedTransfer.Headers` | SIP headers from BYE message (JSON) |

### Failure Codes

| Code | Description | Typical handling |
|---|---|---|
| 1 | Invalid number | Play error → Disconnect |
| 2 | Busy | Play "line is busy" → Disconnect or retry |
| 3 | No answer (timeout) | Play "no answer" → Disconnect or queue to fallback |
| 5 | Unsupported DN (EP-DN or agent's own DN) | Play error → Disconnect |
| 6 | System error | Play error → Disconnect |
| 48 | Can't transfer after queueing or agent assigned | Play error → Disconnect |

### Wiring Pattern

```
Play Message ("Connecting you to...") → Bridged Transfer ({{Extension}}, timeout: 30s)
  │
  ▼ (call returns here)
Condition: {{BridgedTransfer_dxm.FailureCode}} == 0
  ├── TRUE (connected, third party hung up) → Disconnect Contact
  └── FALSE (failed) → Play Message (error) → Disconnect Contact
```

### Restrictions

- Cannot be added to the Queue Contact activity
- Do not introduce a Bridged Transfer activity later in the flow for contacts that are parked, queued, or assigned to an agent. This may lead to an unsupported flow error.
- Cannot be used in outbound call flows
- Cannot be added in Event flows
- Available on VPOP and Webex Calling platforms only
- Self-loop limit: 75

### Dequeue Behavior

Bridged Transfer has an implicit dequeue enhancement. From Cisco docs:

> "Bridged Transfer is enhanced to dequeue the contact when sending a contact to a third-party interactive voice response (IVR) or automatic call distribution (ACD). If the contact is not handled in the third-party system, it can be taken back to the original queue."

**Example use case:** Queue a call against WxCC agents for a brief period (e.g., 60 seconds). If no agent is available, Bridged Transfer (with implicit dequeue) sends the call to an external call center.

**Contradiction with Restrictions:** The dequeue enhancement describes a queue-then-transfer use case, but the Restrictions section warns "Do not introduce a Bridged Transfer activity later in the flow for contacts that are parked, queued, or assigned to an agent. This may lead to an unsupported flow error." These statements conflict — the dequeue enhancement explicitly supports post-queue usage, but the restriction warns against it. Test this behavior in your environment before relying on it.

### Blind Transfer vs Bridged Transfer

| Aspect | Blind Transfer | Bridged Transfer |
|---|---|---|
| Flow control retained? | No — call leaves system | Yes — call returns on completion/failure |
| Output paths | Terminal (none) | Non-terminal (flow continues) |
| Timeout setting | None | 1–120 seconds |
| Failure codes | 2 (codes 48, 6) | 6 (codes 1, 2, 3, 5, 6, 48) |
| DTMF output digits | No | Yes (up to 32 chars) |
| Use after queueing? | No (code 48) | No (code 48) |

---

