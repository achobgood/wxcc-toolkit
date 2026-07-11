---
description: Enforces mandatory doc lookups for any Flow Designer question
---

# Flow Designer Questions — Doc Lookup Required

When answering ANY question about WxCC Flow Designer (activities, settings, restrictions, capabilities, error codes, event flows, wiring rules, or "can I do X?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any Flow Designer question is: **"I don't have that documented in the Flow Designer reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. Read `docs/reference/flow-designer-essentials.md` (essential activities)
2. If the question involves a situational activity: read `docs/reference/flow-designer-activities/_index.md`, then read the specific activity file (e.g., `docs/reference/flow-designer-activities/bridged-transfer.md`)
3. If the question involves patterns/advanced topics: read `docs/reference/flow-designer-patterns.md`
4. If the question involves FlowIR, programmatic flow building, activity property names for the API, or the v2 REST API: read `docs/reference/flow-designer-flowir.md`

## Hard Rules

- NEVER answer a Flow Designer question from training data or memory alone
- NEVER say "I believe..." or "typically..." about Flow Designer — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every field name, output variable, restriction, and configuration value must trace to a line in the docs

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "The maximum telephony queue time is 86,400 seconds (24 hours) [source: flow-designer-essentials.md § Queue Contact]"
- "The Callback activity requires an ANI variable [source: flow-designer-activities/callback.md § Required Settings]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the Flow Designer reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `fd-essentials-v1`, `fd-patterns-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
