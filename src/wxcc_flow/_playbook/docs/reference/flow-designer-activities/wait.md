## Wait Activity

Pauses flow execution for a specified duration before continuing to the next activity.

### Configuration

| Field | Description |
|---|---|
| Activity Label | Name for the activity |
| Activity Description | Optional description |
| Duration | Time to wait in HH:MM:SS format. Range: **10 seconds** (00:00:10) to **72 hours** (72:00:00). |

### Output Variables

No output variables are available in this activity.

### Use Cases

- **Retry delay:** Wait before retrying a failed HTTP Request
- **Pacing:** Insert a pause between rapid-fire activities to avoid rate limiting
- **Timed announcements:** Wait between periodic queue position announcements
- **Callback retry:** Use the Wait activity in the **CallbackFailed** event and specify the wait period before retrying the callback

### Output Paths

Single default exit. No error-specific output edges.

### Failure Codes

No failure codes are documented for the Wait activity. The activity does not expose error code or error description output variables.

### Restrictions

- Not recommended when an IVR session is active — the IVR session may timeout during a long wait, causing the contact to experience dead air resulting in call failures.
- Don't use the Wait activity in use cases that require high precision — execution may deviate by a few milliseconds from the configured duration.
- **Surge limits:** Wait is a flow-control activity and is subject to system-configured surge limits (separate from per-activity self-loop limits) to ensure stability and prevent infinite looping. See [self-loop-limits.md](self-loop-limits.md) for details.

---

