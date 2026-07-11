---
description: Enforces mandatory doc lookups for any Webex Connect question
---

# Webex Connect Questions — Doc Lookup Required

When answering ANY question about Webex Connect (flow structure, node configuration, HTTP Request nodes, Branch nodes, Evaluate nodes, voice nodes, channel-specific nodes, variable picker syntax, Flow Outcomes, Custom Connectors, Start node triggers, flow wiring, or "how do I do X in Connect?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any Webex Connect question is: **"I don't have that documented in the Webex Connect reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. **Always read `docs/reference/webex-connect.md` first** — core flow structure, node inventory, variable syntax, Flow Outcomes, Custom Connectors
2. If the question involves Branch, Evaluate, voice nodes, or channel-specific nodes: read `docs/reference/webex-connect-advanced.md`
3. If the question involves a specific channel, read the channel doc:
   - SMS/MMS → `docs/reference/connect-sms.md`
   - Email → `docs/reference/connect-email.md`
   - RCS → `docs/reference/connect-rcs.md`
   - Apple Messages → `docs/reference/connect-apple-messages.md`
   - WhatsApp → `docs/reference/connect-whatsapp.md`
   - Multi-channel routing → `docs/reference/connect-multi-channel.md`
4. If the question involves building an action flow: read `docs/playbooks/connect-flows.md`

## Hard Rules

- NEVER answer a Webex Connect question from training data or memory alone
- NEVER say "I believe..." or "typically..." about Connect nodes, headers, variable syntax, or flow wiring — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every node name, header value, variable path, output variable, and configuration value must trace to a line in the docs
- NEVER generate or structurally modify Connect flow JSON — it is a proprietary format with internal UUIDs

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "The HTTP Request node requires `Content-Type: application/json` in the Headers section [source: webex-connect.md § HTTP Request Node]"
- "Use `$(n2.HTTPResponse.responseBody)` to access the response [source: webex-connect.md § Variable Picker Syntax]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the Webex Connect reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `webex-connect-v1`, `connect-advanced-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
