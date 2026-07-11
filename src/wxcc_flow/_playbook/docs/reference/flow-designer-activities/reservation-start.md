## Reservation Start Event

> **Documentation pending — not yet verified against Cisco help docs.**
>
> This event handler exists as a shape in the [Cloverhound WxCC Flow Builder Activity Library](https://github.com/Cloverhound/Webex-CC-Flow-Builder-Activity-Library) but could not be verified against the official Cisco help documentation at help.webex.com as of May 2025.

### What We Know

- **Category:** Event (event handler on the Event Flows canvas)
- **Cloverhound shape dimensions:** 230×146 (same as other event shapes)
- **Likely purpose:** Fires when the routing engine reserves an agent for a contact — the step between queue selection and agent offer. In WxCC routing, a "reservation" occurs when the system identifies an available agent and holds them before the call is offered.

### What Needs Verification

Before using this event in documentation or flow instructions, verify the following against the Cisco help docs or a live WxCC tenant:

- [ ] Exact event handler name in the Flow Designer UI (e.g., `ReservationStart`, `AgentReserved`, or another variant)
- [ ] When exactly this event fires relative to `AgentOffered` and `AgentAccepted`
- [ ] Output variables exposed by this event handler
- [ ] Which main flow activities must be present for this event to appear on the Event Flows canvas
- [ ] Restrictions on which activities can be used inside this event handler

---
