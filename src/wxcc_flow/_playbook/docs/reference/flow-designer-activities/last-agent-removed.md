## Last Agent Removed Event

> **Documentation pending — not yet verified against Cisco help docs.**
>
> This event handler exists as a shape in the [Cloverhound WxCC Flow Builder Activity Library](https://github.com/Cloverhound/Webex-CC-Flow-Builder-Activity-Library) but could not be verified against the official Cisco help documentation at help.webex.com as of May 2025.

### What We Know

- **Category:** Event (event handler on the Event Flows canvas)
- **Cloverhound shape dimensions:** 230×146 (same as other event shapes)
- **Likely purpose:** Fires when the last agent is removed from (or disconnects from) the interaction — for example, after a conference call where the last remaining agent hangs up, leaving only the caller. This may differ from `AgentDisconnected` (which fires when *any* agent disconnects) and `PhoneContactEnded` (which fires when the entire contact terminates).

### What Needs Verification

Before using this event in documentation or flow instructions, verify the following against the Cisco help docs or a live WxCC tenant:

- [ ] Exact event handler name in the Flow Designer UI (e.g., `LastAgentRemoved`, `LastAgentDisconnected`, or another variant)
- [ ] When exactly this event fires relative to `AgentDisconnected` and `PhoneContactEnded`
- [ ] Whether this event fires only in multi-agent scenarios (conference, consult transfer) or also for single-agent calls
- [ ] Output variables exposed by this event handler
- [ ] Which main flow activities must be present for this event to appear on the Event Flows canvas
- [ ] Restrictions on which activities can be used inside this event handler

---
