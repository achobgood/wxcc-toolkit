---
description: Enforces mandatory doc lookups for any WxCC Control Hub / platform question
---

# WxCC Platform / Control Hub Questions — Doc Lookup Required

When answering ANY question about WxCC Control Hub configuration (entry points, queues, teams, sites, PSTN assignment, channel assets, routing strategy, global variables, CCAI config, Analyzer reporting, Service Apps, CJDS, or "where do I configure X in Control Hub?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any WxCC platform question is: **"I don't have that documented in the WxCC platform reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. **Always read `docs/reference/wxcc-platform.md` first** — Control Hub entities, global variables, CCAI config, Analyzer, tenant setup
2. If the question involves initial setup or entry point/queue creation: read `docs/playbooks/wxcc-setup.md`
3. If the question involves Webex API authentication or Service Apps: read `docs/playbooks/webex-api-auth.md`
4. If the question involves CJDS (Customer Journey Data Service): read `docs/playbooks/cjds-integration.md`

## Hard Rules

- NEVER answer a WxCC platform question from training data or memory alone
- NEVER say "I believe..." or "typically..." about Control Hub navigation, entity configuration, global variable names, or CCAI settings — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every Control Hub path, field name, global variable name, queue setting, and routing configuration must trace to a line in the docs
- Control Hub, Webex Connect, AI Agent Studio, and Flow Designer are FOUR DIFFERENT UIs — never combine steps across UIs in a single instruction

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "Create the entry point at Control Hub → Contact Center → Entry Points [source: wxcc-platform.md § Entry Points]"
- "The global variable `Global_Language` must be set as Agent Viewable [source: wxcc-platform.md § Global Variables]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the WxCC platform reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `wxcc-platform-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
