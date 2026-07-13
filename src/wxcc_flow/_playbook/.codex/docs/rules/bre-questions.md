---
description: Enforces mandatory doc lookups for any Business Rules Engine question
---

# BRE (Business Rules Engine) Questions — Doc Lookup Required

When answering ANY question about the WxCC Business Rules Engine (DataSync, rules, CSV upload, BRE Request activity, data tables, sizing limits, lookup patterns, or "how do I use BRE for X?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any BRE question is: **"I don't have that documented in the BRE reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. **Always read `docs/reference/bre.md` first** — DataSync, rules, data tables, sizing limits, comparison with other data sources
2. If the question involves setup or CSV upload: read `docs/playbooks/bre-setup.md`
3. If the question involves the BRE Request activity in Flow Designer: read the activity file in `docs/reference/flow-designer-activities/` (check `_index.md` for the filename)
4. If the question involves choosing BRE vs. other data backends: also read `docs/reference/db-integration.md` for the comparison

## Hard Rules

- NEVER answer a BRE question from training data or memory alone
- NEVER say "I believe..." or "typically..." about BRE data tables, rule syntax, sizing limits, or DataSync configuration — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every table limit, rule syntax, field name, and configuration step must trace to a line in the docs

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "BRE data tables support a maximum of 5000 rows [source: bre.md § Sizing Limits]"
- "Upload CSV files via DataSync at Control Hub → Contact Center → BRE [source: bre-setup.md § CSV Upload]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the BRE reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `bre-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
