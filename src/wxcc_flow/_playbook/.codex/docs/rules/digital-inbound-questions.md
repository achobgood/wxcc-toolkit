---
description: Enforces mandatory doc lookups for any digital inbound agent question
---

# Digital Inbound Questions — Doc Lookup Required

When answering ANY question about digital inbound AI agent flows (channel-specific Start triggers, Webex Engage conversation nodes, Process Message, multi-turn conversation loops, human agent escalation, Queue Task, Fetch Conversation Transcript, cross-channel escalation, or "how do I set up a digital channel for my agent?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any digital inbound question is: **"I don't have that documented in the digital inbound reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. **Always read `docs/reference/digital-inbound.md` first** — architecture, channel triggers, Webex Engage wiring, Process Message, escalation, multi-turn loops, Live Chat extras, Fetch Conversation Transcript
2. If the question involves building the flow step-by-step: read `docs/playbooks/digital-inbound-agent.md`
3. If the question involves cross-channel escalation (chat → voice): read `docs/playbooks/cross-channel-escalation.md`
4. If the question involves a specific channel's nodes: read the appropriate channel doc in `docs/reference/connect-*.md`

## Hard Rules

- NEVER answer a digital inbound question from training data or memory alone
- NEVER say "I believe..." or "typically..." about channel triggers, Webex Engage nodes, Process Message configuration, or escalation patterns — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every node name, variable path, channel-specific configuration, and escalation step must trace to a line in the docs
- Digital inbound and outbound notification are DIFFERENT flow patterns — never confuse them

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "The Process Message node sends the customer message to the AI agent and returns the response [source: digital-inbound.md § Process Message]"
- "Cross-channel escalation requires writing the transcript to CJDS before initiating the voice call [source: cross-channel-escalation.md § Transcript Handoff]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the digital inbound reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `digital-inbound-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
