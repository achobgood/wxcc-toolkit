---
description: Enforces mandatory doc lookups for any AI Agent Studio (scripted) question
---

# AI Agent Studio (Scripted) Questions — Doc Lookup Required

When answering ANY question about scripted AI agents in AI Agent Studio (intents, entities, responses, fulfillment, AI engines, context flow, training phrases, Incoming Custom Events, state_update, voice channel fulfillment, or "how do I set up a scripted agent?"), you MUST read the authoritative docs before responding.

## Default Position

Your starting answer to any scripted AI agent question is: **"I don't have that documented in the scripted agent reference."** Only replace this with a substantive answer after completing the lookup sequence below AND finding a citable source. If the lookup finds nothing, the default stands — do not fill the gap from training data.

## Mandatory Lookup Sequence

1. **Always read `docs/reference/ai-agent-studio-scripted.md` first** — intents, entities, responses, fulfillment patterns, AI engines, context flow, voice fulfillment, Incoming Custom Events
2. If the question involves scripted agent design (choosing intents, entity design, conversation flow): read `docs/playbooks/scripted-agent-design.md`
3. If the question involves building/deploying a scripted agent: read `docs/playbooks/scripted-agent-build.md`
4. If the question involves voice channel fulfillment with Flow Designer: also read `docs/reference/flow-designer-patterns.md` § Scripted Agent Fulfillment Pattern

## Hard Rules

- NEVER answer a scripted agent question from training data or memory alone
- NEVER say "I believe..." or "typically..." about intents, entities, fulfillment, AI engines, or context flow — either cite the doc or say "I don't have that documented"
- If the doc doesn't cover the user's question, say so explicitly — do not fill the gap with plausible-sounding invented details
- Every intent name, entity type, response template, fulfillment pattern, and AI engine option must trace to a line in the docs
- Scripted agents do NOT use actions with LLM-driven descriptions — that is the autonomous pattern. Never confuse the two.
- Scripted agent fulfillment for digital channels uses inline flow logic (Data Parser → Branch → HTTP → Evaluate → Channel Reply), NOT standalone action flows

## Citation Requirement

Every platform-specific claim in your response MUST include an inline citation:

Format: `[source: filename § section heading]`

Examples:
- "Scripted agents support Rasa, Dialogflow ES, Dialogflow CX, and native NLU engines [source: ai-agent-studio-scripted.md § AI Engines]"
- "Voice fulfillment uses a Custom Event response that triggers Flow Designer [source: ai-agent-studio-scripted.md § Voice Channel Fulfillment]"

If you cannot produce a citation for a claim, replace the claim with: "I don't have that documented in the scripted agent reference."

This is not optional formatting — a missing citation means an unverified claim, which means potential hallucination.

## Proof of Read

Each primary reference doc contains a `<!-- ref-tag: xxx -->` comment near the top. When answering, state the ref-tags from every doc you consulted:

> Docs consulted: `ai-agent-scripted-v1`

If you cannot produce the ref-tag for a doc you're citing, you did not read the current version. Do not cite it.
