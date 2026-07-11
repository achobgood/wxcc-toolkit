---
description: Enforces mandatory doc lookups for any database integration question
---

# Database Integration Questions — Doc Lookup Required

When answering ANY question about database integration patterns for WxCC (Supabase, PostgREST, multi-backend selection, HTTP headers for DB calls, research protocol, or "what database should I use for X?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any database integration question is: **"I don't have that documented in the database integration reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. **Always read `docs/reference/db-integration.md` first** — multi-backend comparison, selection criteria, research protocol, HTTP patterns
2. If the question involves Supabase specifically: read `docs/playbooks/supabase.md` — schema, migrations, PostgREST API, headers, debugging
3. If the question involves BRE as a data source: also read `docs/reference/bre.md` for the comparison

## Hard Rules

- NEVER answer a database integration question from training data or memory alone
- NEVER say "I believe..." or "typically..." about Supabase headers, PostgREST query syntax, or backend selection criteria — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every header name, header value, query parameter, API endpoint pattern, and selection criterion must trace to a line in the docs
- The research protocol in `db-integration.md` exists for a reason — when the user's backend isn't documented, follow the protocol instead of guessing

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "Supabase PostgREST requires `apikey` and `Authorization` headers on every request [source: supabase.md § HTTP Headers]"
- "For datasets under 5000 rows with simple key-value lookups, BRE is preferred over an external database [source: db-integration.md § Backend Selection]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the database integration reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `db-integration-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
