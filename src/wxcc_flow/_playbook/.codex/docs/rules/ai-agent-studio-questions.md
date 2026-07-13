---
description: Enforces mandatory doc lookups for any AI Agent Studio (autonomous) question
---

# AI Agent Studio (Autonomous) Questions — Doc Lookup Required

When answering ANY question about autonomous AI agents in AI Agent Studio (agent goal, welcome message, action configuration, action descriptions, slot entities, sample JSON, agent instructions, Custom Data, Custom Event Fulfillment, CCAI config, deployment, or "how do I configure X in Agent Studio?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any AI Agent Studio (autonomous) question is: **"I don't have that documented in the AI Agent Studio reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. **Always read `docs/reference/ai-agent-studio.md` first** — agent configuration, actions, slots, descriptions, instructions, CCAI, deployment, Custom Data, Custom Event Fulfillment
2. If the question involves the Connect flow backing an action: read `docs/reference/webex-connect.md` and `docs/playbooks/connect-flows.md`
3. If the question involves deployment or CCAI wiring: also check `docs/reference/wxcc-platform.md` for Control Hub steps
4. If the question involves the agent import/export JSON, one-step agent import, or the `bot_type`/`configuration`/`tools` structure: read `docs/reference/ai-agent-studio-import-json.md`

## Hard Rules

- NEVER answer an AI Agent Studio question from training data or memory alone
- NEVER say "I believe..." or "typically..." about agent configuration, action descriptions, slot syntax, or deployment steps — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every field name, configuration value, instruction pattern, and deployment step must trace to a line in the docs
- Action descriptions use `{{variable_name}}` for slot references — NEVER guess the syntax; confirm from docs
- The primary build artifact is the AI Agent in AI Agent Studio, not the routing node — lead with agent configuration

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "Set the Agent Goal to a single sentence describing what the agent does [source: ai-agent-studio.md § Agent Configuration]"
- "Action descriptions must use `{{customer_id}}` syntax for slot references [source: ai-agent-studio.md § Action Descriptions]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the AI Agent Studio reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `ai-agent-studio-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
