# WxCC AI Agent Builder Toolkit

Build AI agents and flows for Webex Contact Center with guided Claude Code assistance.

## Execution Rules

These rules apply to ALL builds — AI agent flows, standalone Connect flows, WxCC Flow Designer flows, outbound notifications, inbound voice IVRs, BRE lookups, and any other platform configuration. They are not limited to the AI Agent path.

### Platform Knowledge Rule

NEVER answer questions about any Cisco platform from training data. This includes:
- **Webex Connect**: flow structure, node configuration (HTTP Request, Branch, Evaluate, Play, Call User, Voice Node Group, Channel nodes, etc.), variable picker syntax, Flow Outcomes, Start node triggers, flow wiring
- **WxCC Flow Designer**: Virtual Agent V2, Queue Contact, Collect Input, Play Message, Call Patch, BRE Request, Functions Activity, flow variables, entry point routing
- **AI Agent Studio**: agent configuration (autonomous or scripted), action descriptions, intents, entities, slot management, instruction authoring, CCAI config, deployment
- **WxCC Control Hub**: entry points, queues, teams, sites, PSTN assignment, channel assets, routing strategy
- **Webex APIs**: Service Apps, token refresh, Custom Connectors, CJDS, Webex Calling integration

Every platform instruction — UI fields, node settings, header values, deployment steps, routing configuration — must come from a file in `docs/reference/` or `docs/playbooks/`. If you can't find it in the docs, say "I don't have that documented" and either search the project docs or tell the user it needs to be added. Inventing a plausible-sounding platform detail is the single most damaging failure mode in this project — the user has no way to know it's wrong until it fails at runtime.

### Step Completeness Rule

The target user has ZERO prior experience with WxCC, Webex Connect, AI Agent Studio, or Flow Designer. This applies whether they're building an AI agent, a standalone Connect flow, an inbound voice IVR, an outbound notification, or a BRE lookup. Every instruction must:
- Name the exact platform and UI location (e.g., "Webex Connect → HTTP Request node → Headers section", "Control Hub → Contact Center → Queues → Create Queue", "Flow Designer → Call Patch node → Caller ID field")
- Specify the exact value to enter or select, not just "configure it"
- Include the exact click path when navigating between platforms (Connect, Control Hub, AI Agent Studio, and Flow Designer are four different UIs)
- Never assume a previous step was already completed unless the user explicitly confirmed it
- Never say "as you did before" — repeat the instruction or link to where it was given
- Never combine platform steps across different UIs in a single bullet — each platform switch is a distinct step

If you're about to write "configure the [X]" without saying exactly where and how, stop and look it up in `docs/`.

### Skill Invocation Rule

When the agent file or a skill says "YOU MUST call Skill(X)" or "Step 1: Load references — read these docs," that is not a suggestion. The reference docs contain platform-specific conventions that CANNOT be guessed correctly from training data — this applies to Connect node wiring, Flow Designer activities, AI Agent Studio configuration, Control Hub setup, and all outbound/inbound flow patterns alike.

If you skip the skill invocation or skip reading the reference docs, the output WILL contain invented details that don't match the actual platform behavior.

### Don't Ask What Users Can't Answer

Before surfacing an open question, ask yourself: "Can the user reasonably answer this, or should I answer it from platform knowledge?" Only ask questions the user has context to answer — business logic, their data schema, their team's preferences.

Never ask the user for:
- API response shapes (they don't know what the API returns — provide a sample and explain it)
- Data center regions or endpoint URLs (tell them where to look it up in Control Hub)
- Event type conventions or naming patterns (provide a recommended convention)
- Failure handling defaults (provide a recommended default with rationale, let them override)
- Node settings, header values, or variable syntax (these come from docs, not the user)

### Flow Designer Lookups — MANDATORY for Any Question

**Trigger:** ANY user question that mentions or relates to Flow Designer — activities, settings, restrictions, capabilities, error codes, event flows, configuration fields, or "can I do X in Flow Designer?" — REQUIRES reading docs before answering. This applies even for questions that seem simple, common, or that you feel confident about. Training data is stale; the docs are authoritative.

**You MUST NOT answer a Flow Designer question from memory or training data.** If you catch yourself about to answer without having issued a Read tool call to a file in `docs/reference/flow-designer-*` in this turn, STOP and read first.

**Lookup procedure** (designed for token efficiency — the reference is split across files):
1. **Always read `docs/reference/flow-designer-essentials.md` first** — contains the 9 activities every flow uses
2. If the question is about a situational activity, read `docs/reference/flow-designer-activities/_index.md` for available activity files
3. Read the specific activity file directly (e.g., `docs/reference/flow-designer-activities/bridged-transfer.md`)
4. For patterns/advanced topics (versioning, subflows, fulfillment, TTS, debugging), read `docs/reference/flow-designer-patterns.md`

**If the answer isn't in the docs:** Say "I don't have that documented in the Flow Designer reference" — do NOT fill the gap from training data.

### Never Generate Proprietary Export JSON

Never generate or structurally modify Flow Designer **export JSON** (the raw format from the UI export button) or Webex Connect flow JSON. Both formats are proprietary — they contain internal activity UUIDs cross-referenced in process links, diagram widgets, and port mappings with pixel coordinates.

The only safe operation on exported flow JSON is find-and-replace on org-specific UUIDs (orgId, virtualAgentId, queueId, display names).

**FlowIR is different.** FlowIR is the official API format for programmatic flow building via the v2 REST API. It uses activity names (not UUIDs), connector names (not IDs), and event spec names (not IDs) — the server resolves all internal references automatically. Generating FlowIR and pushing it via the API is the supported path for programmatic flow creation. See `docs/reference/flow-designer-flowir.md` for the format, activity property patterns, and validate → create workflow.

### No Abbreviated Documentation

Never use "etc.", "and more", "and others", or vague language when documenting API specs, node configurations, or platform settings. Enumerate every item explicitly. If there are 9 inputs, list all 9. If there are 5 query parameters, list all 5. The user relies on this output as their primary reference — abbreviations mean missing information.

## Quick Start

Run `/wxcc-agent-builder` to start building an agent. It will walk you through everything — from database setup through a working AI agent handling calls.

## Agent Invocation Rules

Spawn `wxcc-agent-builder` **ONCE** at the start of a session. For all subsequent user messages, use `SendMessage` to continue that same agent — do NOT spawn a new agent per question. The agent handles the full workflow (interview, design, build) internally across the entire session.

## If Debugging

Run `/wxcc-debug` to troubleshoot a failing action.

## Flow Designer CLI (`wxcc-flow`)

`wxcc-flow` is the preferred way to interact with Flow Designer programmatically. It wraps the Flow Store REST API (63+ endpoints) and replaces the MCP server integration, which had broken `list_flows`, token rotation issues, and limited coverage (12 of 63+ endpoints).

### Setup

```bash
wxcc-flow configure --token TOKEN --org ORG_ID
```

Token resolution: `WXCC_FLOW_TOKEN` env → `WEBEX_ACCESS_TOKEN` env → `~/.wxcc-flow/config.json`. Project ID is auto-resolved at configure time.

### Key Commands

| Command | Purpose |
|---------|---------|
| `wxcc-flow list` | List all flows (table format) |
| `wxcc-flow export FLOW_ID -o file.json` | Export flow as FlowIR JSON |
| `wxcc-flow validate file.json` | Dry-run validate FlowIR |
| `wxcc-flow create file.json` | Import/create flow from FlowIR |
| `wxcc-flow save-draft FLOW_ID file.json` | Save FlowIR as draft |
| `wxcc-flow publish FLOW_ID` | Publish a draft (REST-only) |
| `wxcc-flow activities` | List all activities (52 on prod as of 2026-07-11) |
| `wxcc-flow describe ACTIVITY` | Activity properties and schema |
| `wxcc-flow global-vars` | List org global variables |

All commands support `--debug` for raw HTTP traces and `-o json` for JSON output where applicable.

### Known CLI Limitations

| Limitation | Workaround |
|------------|------------|
| `wxcc-flow events` cannot list the event-spec catalog — prod exposes no event-spec endpoint | Get event names from an exported flow's `eventFlows` (`wxcc-flow export FLOW_ID`) or `docs/reference/flow-designer-flowir.md` § 6 |

(Cascading/parent choices are supported since 2026-07-11: `wxcc-flow choices ACTIVITY INPUT --parent-input PARENT --parent-value VALUE`.)

### Programmatic Flow Building Workflow

```
wxcc-flow template simple-inbound -o flow.json   # starter FlowIR
# ... edit flow.json with nodes, edges, variables ...
wxcc-flow validate flow.json                      # dry-run check
wxcc-flow create flow.json                        # import to sandbox
wxcc-flow publish FLOW_ID                         # publish draft
```

See `docs/reference/flow-designer-flowir.md` for FlowIR format, tested activity property patterns, and the complete activity registry.

### Pre-approved in Claude Code

`Bash(wxcc-flow:*)` is allowed in `.claude/settings.json` — all commands run without permission prompts.

## File Map

| Path | Purpose |
|------|---------|
| `src/wxcc_flow/` | `wxcc-flow` CLI — wraps Flow Designer REST API (config, client, output, all commands) |
| `.claude/agents/wxcc-agent-builder.md` | Main builder agent — drives the full workflow |
| `.claude/skills/build-action/` | Skill: build Webex Connect flows for autonomous agent actions |
| `.claude/skills/build-scripted-fulfillment/` | Skill: build fulfillment for scripted agent intents (digital + voice) |
| `.claude/skills/configure-ai-agent/` | Skill: configure autonomous agent in AI Agent Studio |
| `.claude/skills/configure-scripted-agent/` | Skill: configure scripted agent in AI Agent Studio (intents, entities, responses, context flow) |
| `.claude/skills/design-scripted-agent/` | Skill: design scripted agent intents/entities/responses/context flow before building |
| `.claude/skills/wxcc-debug/` | Skill: debug failing actions |
| `.claude/skills/build-outbound-flow/` | Skill: build webhook-triggered outbound voice/TTS flows |
| `.claude/skills/build-notification/` | Skill: build outbound notifications (SMS, Email, RCS, Apple Messages, WhatsApp, multi-channel) |
| `.claude/skills/build-digital-inbound/` | Skill: build digital inbound AI agent conversation flows |
| `.claude/skills/design-flow/` | Skill: translate interview answers into a Flow Designer design document using blueprints and activity docs |
| `.claude/skills/build-flow-designer/` | Skill: build WxCC Flow Designer voice flows (IVR, callback, queue treatment, DNIS routing, transfers) |
| `.claude/skills/build-flow-programmatic/` | Skill: build WxCC Flow Designer voice flows programmatically via FlowIR JSON and wxcc-flow CLI |
| `.claude/skills/build-solution-docs/` | Skill: generate HTML architecture diagrams + PPTX solution deck from any plan document |
| `.claude/skills/build-spec-diagram/` | Skill: generate .drawio flow diagram from a design doc in docs/plans/ (3-tab: Summary, Main Flow, Event Flow) |
| `docs/reference/webex-connect.md` | Platform knowledge: Webex Connect flows |
| `docs/reference/ai-agent-studio.md` | Platform knowledge: AI Agent Studio (autonomous agents) |
| `docs/reference/ai-agent-studio-import-json.md` | Platform knowledge: AI Agent Studio autonomous-agent import/export JSON schema (`bot_type`/`configuration`/`tools`) for one-step agent import, verified against real Cisco exports |
| `docs/reference/ai-agent-studio-scripted.md` | Platform knowledge: AI Agent Studio (scripted agents) |
| `docs/reference/wxcc-platform.md` | Platform knowledge: WxCC Control Hub, CCAI, Global Variables, tenant config |
| `docs/reference/wxcc-provisioning-api.md` | Platform knowledge: WxCC Provisioning API for programmatic resource creation (teams, queues, business hours, entry points) via REST |
| `docs/reference/flow-designer-essentials.md` | Platform knowledge: Flow Designer essential activities (Play Message, Play Music, Set Variable, Variable Types, Output Variables, Global Events, Queue Contact, Disconnect, Voice Flow Basics) |
| `docs/reference/flow-designer-activities/` | Platform knowledge: Flow Designer situational activities (one file per activity, see _index.md) |
| `docs/reference/flow-designer-patterns.md` | Platform knowledge: Flow Designer patterns (versioning, subflows, dynamic variables, fulfillment pattern, connectors auth, TTS, expression builder, debugging, CJDS node, management API) |
| `docs/reference/flow-designer-flowir.md` | Platform knowledge: FlowIR format for programmatic flow building (v2 REST API, 28 round-trip tested activity property patterns, component type summary, activity registry, validate/create workflow, import field overrides, gotchas) |
| `docs/reference/db-integration.md` | Multi-backend DB patterns + research protocol |
| `docs/reference/bre.md` | Platform knowledge: Business Rules Engine (DataSync, rules, BRE Request activity) |
| `docs/reference/connect-sms.md` | Platform knowledge: SMS & MMS nodes |
| `docs/reference/connect-email.md` | Platform knowledge: Email node |
| `docs/reference/connect-rcs.md` | Platform knowledge: RCS Capability & Message nodes |
| `docs/reference/connect-apple-messages.md` | Platform knowledge: Apple Messages for Business node |
| `docs/reference/connect-whatsapp.md` | Platform knowledge: WhatsApp node |
| `docs/reference/connect-multi-channel.md` | Platform knowledge: multi-channel routing patterns |
| `docs/reference/webex-connect-advanced.md` | Platform knowledge: advanced Connect nodes (Branch, Evaluate, voice nodes, channel nodes) |
| `docs/reference/digital-inbound.md` | Platform knowledge: digital inbound agent architecture |
| `docs/templates/action-config.md` | 10-step output format template |
| `docs/templates/ai-agent-design-doc.md` | Design doc template for AI Agent builds (autonomous + scripted) |
| `docs/templates/ai-agent-studio-import-template.json` | Verified skeleton for the AI Agent Studio autonomous-agent import JSON (filled by `configure-ai-agent` Step 13) |
| `docs/templates/flow-designer-design-doc.md` | Design doc template for Flow Designer voice flows |
| `docs/templates/design-doc.md` | DEPRECATED — replaced by ai-agent-design-doc.md and flow-designer-design-doc.md |
| `docs/reference/flow-blueprints.md` | Common Flow Designer flow patterns (blueprints) with Activities and Connections tables |
| `docs/templates/outbound-flow-config.md` | Outbound flow output format template |
| `docs/templates/notification-config.md` | Multi-channel notification output format template |
| `docs/examples/` | Working examples from real builds |
| `docs/plans/` | Generated design docs (one per agent build) |
| `docs/playbooks/` | Step-by-step platform guides |
| `docs/playbooks/outbound-voice.md` | Playbook: outbound voice calls with TTS in Connect |
| `docs/playbooks/inbound-voice.md` | Playbook: inbound voice call handling in Connect |
| `docs/playbooks/sequential-dialing.md` | Playbook: sequential dialing / on-call connect (Call Patch chaining) |
| `docs/playbooks/webhook-triggers.md` | Playbook: webhook-triggered flows in Connect |
| `docs/playbooks/webex-calling-paging.md` | Playbook: Connect → Webex Calling paging integration |
| `docs/playbooks/outbound-sms.md` | Playbook: outbound SMS/MMS notifications |
| `docs/playbooks/outbound-email.md` | Playbook: outbound email notifications |
| `docs/playbooks/outbound-rcs.md` | Playbook: outbound RCS notifications with SMS fallback |
| `docs/playbooks/outbound-apple-messages.md` | Playbook: outbound Apple Messages notifications with SMS fallback |
| `docs/playbooks/outbound-whatsapp.md` | Playbook: outbound WhatsApp notifications |
| `docs/playbooks/multi-channel-routing.md` | Playbook: multi-channel routing (one flow, all channels) |
| `docs/playbooks/digital-inbound-agent.md` | Playbook: digital inbound AI agent conversations |
| `docs/playbooks/inbound-sms.md` | Playbook: standalone inbound SMS processing (no AI Agent) |
| `docs/playbooks/cjds-integration.md` | Playbook: CJDS region lookup, token setup, API response shape, event types, failure handling |
| `docs/playbooks/scripted-agent-design.md` | Playbook: scripted agent design (intents, entities, context flow, responses) |
| `docs/playbooks/scripted-agent-build.md` | Playbook: scripted agent build (AI Agent Studio config, fulfillment, deploy) |
| `docs/playbooks/webex-api-auth.md` | Playbook: calling Webex APIs from WxCC (Service App, token refresh subflow, Custom Nodes) |
| `docs/playbooks/connect-flows.md` | Playbook: building Webex Connect flows that back AI agent actions |
| `docs/playbooks/supabase.md` | Playbook: Supabase data layer setup (schema, migrations, PostgREST API, debugging) |
| `docs/playbooks/cross-channel-escalation.md` | Playbook: digital chat → voice call escalation with transcript via CJDS |
| `docs/playbooks/bre-setup.md` | Playbook: BRE setup (DataSync access, rules, CSV upload, Flow Designer wiring) |
| `docs/playbooks/wxcc-setup.md` | Playbook: WxCC Control Hub & Flow Designer one-time setup |
| `docs/playbooks/custom-connectors-setup.md` | Playbook: Custom Connector creation (OAuth/Basic Auth, Service App, linking to HTTP Request) |
| `docs/playbooks/functions-setup.md` | Playbook: Functions setup (create, test, publish, use in flow, limits) |
| `docs/playbooks/dual-call-paging.md` | Playbook: dual-call paging pattern (IVR menu triggers parallel outbound page via Create Task API while transferring caller to department) |

Maintainers: platform conventions and gotchas live in `docs/reference/`. Update them when you discover new issues.

## Skill Disambiguation Table

When the user's request could match multiple skills, use this table to route correctly. Both directions of each ambiguity are listed.

| If the user says... | Use this skill | NOT this one (and why) |
|---|---|---|
| "build a flow for my agent action" | `build-action` | NOT `build-digital-inbound` (that's the conversation loop, not a single action) |
| "build an inbound WhatsApp/SMS/chat flow" | `build-digital-inbound` | NOT `build-action` (that's a single action HTTP flow, not a conversation) |
| "build a Connect flow for my agent" | **Ambiguous** — ask: "action flow (single API call) or conversation flow (multi-turn chat loop)?" | |
| "send an outbound SMS/email/WhatsApp" | `build-notification` | NOT `build-outbound-flow` (that's voice-only with Call User node) |
| "build an outbound voice call / TTS alert" | `build-outbound-flow` | NOT `build-notification` (that handles non-voice channels + multi-channel routing) |
| "build an IVR" / "I need a voice flow" | `design-flow` (STEP 1) | NOT `build-flow-designer` (that's STEP 2 — needs the design doc first) |
| "build the flow from this design doc" (manual UI) | `build-flow-designer` (STEP 2) | NOT `design-flow` (that creates the design doc — it already exists); for programmatic path see `build-flow-programmatic` |
| "build the flow from this design doc" (generic) | **Ambiguous** — ask: "Manual UI instructions (build-flow-designer) or programmatic via CLI (build-flow-programmatic)?" | |
| "build my flow programmatically" / "create via CLI" | `build-flow-programmatic` | NOT `build-flow-designer` (that's manual UI instructions, this generates FlowIR JSON) |
| "generate a diagram from this plan" | **Ambiguous** — ask: "activity-level flow diagram (.drawio) or architecture diagrams (HTML + PPTX)?" | |
| "visualize this flow" / "drawio" | `build-spec-diagram` | NOT `build-solution-docs` (that's architecture-level Mermaid, not activity-level .drawio) |
| "create a presentation / deck" | `build-solution-docs` | NOT `obsidian-slides` (MARP format) and NOT Gamma (AI-generated, not plan-based) |
| "configure my AI agent" (mid-build) | `configure-ai-agent` | NOT `wxcc-agent-builder` (that's the full pipeline from scratch — if already mid-build, use the specific skill) |
| "build me an agent from scratch" | `wxcc-agent-builder` agent | NOT individual skills (the agent orchestrates the full pipeline) |
| "design my scripted agent" / "plan intents" | `design-scripted-agent` | NOT `configure-scripted-agent` (that's the build phase — design first) |
| "configure/build my scripted agent" | `configure-scripted-agent` | NOT `configure-ai-agent` (that's autonomous agents only) |
| "set up a scripted agent from scratch" | `design-scripted-agent` first, then `configure-scripted-agent` | NOT a single skill — design precedes build |
| "build fulfillment for my scripted agent" | `build-scripted-fulfillment` | NOT `build-action` (that's for autonomous agent action flows) |
| "my action isn't working" / "debug" | `wxcc-debug` | NOT `build-action` (that builds new actions, doesn't debug existing ones) |
| "action" (AI agent context) | `build-action` (autonomous) | NOT `build-scripted-fulfillment` (scripted agents call it "fulfillment", not "actions") |
| "fulfillment" (AI agent context) | `build-scripted-fulfillment` (scripted) | NOT `build-action` (autonomous agents call it "actions", not "fulfillment") |
| "queue" (voice flow context) | Flow Designer Queue Contact activity | NOT Control Hub queue entity (different UI — see `wxcc-setup.md` for Control Hub queues) |
| "flow for my chatbot" / "bot" | **Ambiguous** — ask: "Starting from scratch (full pipeline), building the conversation loop (digital inbound), or wiring up an API call (action/fulfillment)?" | |
| "outbound notification" / "outbound flow" (no channel) | **Ambiguous** — ask: "Voice call with TTS, digital (SMS/Email/WhatsApp/RCS), or multi-channel with fallback?" | |
| "call flow" / "flow for our contact center" (generic) | **Ambiguous** — ask: "Inbound voice IVR, AI agent, or digital channel (chat/SMS)?" | |
| "wire up the API call for my agent" (no type) | **Ambiguous** — ask: "Autonomous agent action or scripted agent intent?" | |
| "set up my agent in Agent Studio" (no type) | **Ambiguous** — ask: "Autonomous agent (actions + LLM descriptions) or scripted agent (intents + entities)?" Autonomous → `configure-ai-agent`; scripted → `configure-scripted-agent` | |
| "debug my voice flow" / "flow not routing" | No skill — route to `docs/reference/flow-designer-patterns.md` § Debugging | NOT `wxcc-debug` (that covers AI agent actions only, not Flow Designer voice flows) |

## Multi-Skill Workflows

Some goals require multiple skills in sequence. Use this table to avoid picking one skill when the task actually spans several.

| Goal | Skill sequence | Why multi-skill |
|---|---|---|
| New autonomous AI agent from scratch | `wxcc-agent-builder` → (orchestrates: `build-action` → `configure-ai-agent` → `build-digital-inbound`) | Agent drives the full pipeline — don't invoke individual skills directly |
| New Flow Designer voice flow | `design-flow` → [user review] → `build-spec-diagram` (optional) → `build-flow-designer` OR `build-flow-programmatic` → `wxcc-setup.md` playbook | Design must precede build; diagram is optional visual review step |
| Scripted agent with fulfillment | `design-scripted-agent` → [user review] → `configure-scripted-agent` → `build-scripted-fulfillment` (per intent) → `build-digital-inbound` (if digital channel) | Design must precede build; fulfillment is per-intent |
| Multi-channel notification with voice fallback | `build-notification` (digital channels) + `build-outbound-flow` (voice channel) | Voice has a dedicated skill with deeper Call User / Voice Node Group coverage |
| Solution documentation from plan | `build-solution-docs` (HTML + PPTX) and/or `build-spec-diagram` (.drawio) | Different output formats for different audiences — can run both |
| Digital inbound with cross-channel escalation | `build-digital-inbound` → `cross-channel-escalation.md` playbook → `design-flow` (for the voice leg) | Chat-to-voice handoff spans Connect and Flow Designer |

## Sync Checklist (Preventing Config Drift)

Autonomous and scripted agent paths share some content. When updating one, check the other. Files with shared sections have `<!-- SYNC: ... -->` comment markers.

| When you change... | Also update... |
|---------------------|---------------|
| Deployment steps in `ai-agent-studio.md` | `ai-agent-studio-scripted.md` Deployment section |
| Deployment steps in `ai-agent-studio-scripted.md` | `ai-agent-studio.md` Deploying / CCAI Config sections |
| Testing guidance in either AI Studio reference | The other AI Studio reference |
| Supabase headers in `build-action/reference.md` | `build-scripted-fulfillment/reference.md` headers table |
| Supabase headers in `build-scripted-fulfillment/reference.md` | `build-action/reference.md` headers table |
| Q3/Q6/Q7/Q8 in `wxcc-agent-builder.md` | These questions are shared — changes affect both agent types |
| Channel-specific variables in `digital-inbound.md` | `ai-agent-studio-scripted.md` (Scripted-Only Features table) |
| Prohibited nodes list in `wxcc-agent-builder.md` | `webex-connect.md` if the list differs |
| New channel support | All three: reference doc, playbook, `digital-inbound.md`, agent builder Q3 |
| New AI engine option | `ai-agent-studio-scripted.md` AI Engines section |
| Voice node sections in `webex-connect-advanced.md` | `outbound-voice.md` Voice Node Group inventory |
| Voice Node Group inventory in `outbound-voice.md` | `webex-connect-advanced.md` voice node sections |
| Call Transfer availability notes | Check if region restrictions change (currently: not London/Europe) |
| HTTP Connector section in `flow-designer-activities/` | `webex-connect.md` disambiguation note; `db-integration.md` if Flow Designer auth patterns referenced |
| Flow Designer scripted fulfillment pattern in `flow-designer-patterns.md` | `ai-agent-studio-scripted.md` Voice Channel Fulfillment section (cross-reference) |
| Voice Channel Fulfillment in `ai-agent-studio-scripted.md` | `flow-designer-patterns.md` Scripted Agent Fulfillment Pattern section |
| Token refresh subflow in `flow-designer-patterns.md` | `webex-api-auth.md` Pattern 2 section |
| Custom Nodes section in `webex-connect.md` | `webex-api-auth.md` Pattern 3 section |
| Service App setup in `cjds-integration.md` | `webex-api-auth.md` (CJDS is one use case; playbook covers general pattern) |
| Evaluate node engine description in `webex-connect-advanced.md` | `inbound-sms.md` engine note (both must agree on let/const support) |
| Pebble filters in `flow-designer-essentials.md` | Functions section in `flow-designer-activities/` (Functions vs. Pebble guidance table) |
| Multilingual TTS in `flow-designer-patterns.md` | Voice playbooks if they reference TTS configuration |
| Live Chat extras in `digital-inbound.md` | `webex-connect-advanced.md` Evaluate examples (parsing patterns) |
| Fetch Conversation Transcript node in `digital-inbound.md` | `cross-channel-escalation.md` (node config must match) |
| CJDS transcript event pattern in `cjds-integration.md` | `cross-channel-escalation.md` (event structure must match) |
| Cross-channel escalation in `cross-channel-escalation.md` | `digital-inbound.md` §4b, `cjds-integration.md` §8 cross-channel section |
| Q6 cross-channel follow-up in `wxcc-agent-builder.md` | `cross-channel-escalation.md` playbook reference |
| BRE Request activity in `flow-designer-activities/` | `bre.md` (full reference must match summary) |
| BRE section in `db-integration.md` | `bre.md` (comparison table, sizing limits must match) |
| BRE data source in `wxcc-agent-builder.md` Q7 | `bre-setup.md` playbook reference |
| Flow Versioning in `flow-designer-patterns.md` | `wxcc-setup.md` publish steps (version label reference) |
| Percentage Allocation in `flow-designer-patterns.md` | Analyzer Reporting subsection in `wxcc-platform.md` (A/B test pattern cross-reference) |
| Subflows general section in `flow-designer-patterns.md` | Token Refresh Subflow section (must not contradict general subflow docs) |
| Subflows general section in `flow-designer-patterns.md` | `webex-api-auth.md` Pattern 2 (subflow references must stay consistent) |
| Analyzer Reporting in `wxcc-platform.md` | `CustomAIAgentInteractionOutcome` in `flow-designer-patterns.md` Scripted Agent Fulfillment section (same variable names) |
| Custom Data section in `ai-agent-studio.md` | `ai-agent-studio-scripted.md` Welcome Message custom data mention; `flow-designer-activities/` VAV2 State Event Settings table |
| Custom Event Fulfillment in `ai-agent-studio.md` | `flow-designer-patterns.md` Scripted Agent Fulfillment Pattern "also applies" note |
| Incoming Custom Events in `ai-agent-studio-scripted.md` | `flow-designer-activities/` VAV2 State Event Settings table (row 2); `ai-agent-studio.md` Custom Event Fulfillment section |
| `{{variable_name}}` rule in `ai-agent-studio.md` | `wxcc-agent-builder.md` Action Descriptions critical rule (must match the distinction) |
| state_update examples in `ai-agent-studio-scripted.md` | `flow-designer-patterns.md` State Event Resume Mechanism (concepts must align) |
| Voice follow-up questions in `wxcc-agent-builder.md` | `ai-agent-studio.md` Custom Data / Custom Event Fulfillment sections (features referenced must exist) |
| Custom Connectors in `flow-designer-activities/` | `wxcc-debug/reference.md` troubleshooting rows, `build-scripted-fulfillment/SKILL.md` Step 7v, `webex-api-auth.md` Pattern 4 |
| Flow Management API in `flow-designer-patterns.md` | `webex-connect.md` limitations table (cross-ref row) |
| Pebble filters (`replace`/`split`/`join`) in `flow-designer-essentials.md` | Check if any playbook examples reference the old "replace is broken" guidance |
| SSML tags in `flow-designer-patterns.md` (Cisco TTS) | `outbound-voice.md` covers Azure Neural TTS — different engines, keep both |
| New Flow Designer activity added to `flow-designer-activities/` | `flow-designer-activities/_index.md` (add row), `build-flow-designer/reference.md` Activity Finder table (add row), `design-flow/reference.md` Activity Quick Reference table (add row) |
| Port definitions or category colors in `build-spec-diagram/reference.md` | `flow-designer-activities/` port names and `flow-designer-essentials.md` activity categories must match |
| Blueprint list in `flow-blueprints.md` | `design-flow/reference.md` Blueprint Selection Guide (must list same blueprints) |
| Activity ports in `flow-designer-activities/` | `design-flow/reference.md` Activity Quick Reference table and Port Name Canonical Map (ports must match); `build-spec-diagram/reference.md` PORT_DEFINITIONS (port names must stay consistent — spec-diagram may use simplified names but must map correctly) |
| Blueprint connection graphs in `flow-blueprints.md` | `flow-designer-design-doc.md` template Connections table format (must match) |
| AI Agent design doc template sections in `ai-agent-design-doc.md` | Build skills that consume it: `build-action`, `configure-ai-agent`, `configure-scripted-agent`, `design-scripted-agent`, `build-digital-inbound`, `build-scripted-fulfillment` |
| Flow Designer design doc template sections in `flow-designer-design-doc.md` | Build skills that consume it: `design-flow`, `build-flow-designer`, `build-spec-diagram` |
| Voice Flow Activities/Connections in `ai-agent-design-doc.md` | Blueprint 11/12 in `flow-blueprints.md` (tables must match) |
| Blueprint 13 (Single-Menu Multilingual) in `flow-blueprints.md` | `design-flow/reference.md` Blueprint Selection Guide and Composition Patterns |
| Blueprint 14 (Dynamic Business Hours) in `flow-blueprints.md` | `design-flow/reference.md` Blueprint Selection Guide |
| Custom Connectors setup in `custom-connectors-setup.md` | `custom-connectors.md` activity doc (setup steps must match) |
| Functions setup in `functions-setup.md` | `functions-activity.md` activity doc (runtime/limits must match) |
| Error port convention in `flow-designer-design-doc.md` | `design-flow/SKILL.md`, `build-spec-diagram/SKILL.md`, `build-flow-designer/SKILL.md`, `design-flow/reference.md` |
| Activity port definitions in `flow-designer-activities/` | `flow-designer-flowir.md` §8 Activity Registry table (output ports must match) |
| Activity registry or property tables in `flow-designer-flowir.md` | `flow-designer-activities/` port names and activity docs (must stay consistent) |
| Property tables in `flow-designer-flowir.md` §7/§7b | `build-flow-programmatic/reference.md` validated patterns |
| `build-flow-programmatic` skill steps | `flow-designer-flowir.md` §9 Validate → Create Workflow (must stay consistent) |
| Flow Designer pipeline in `flow-designer-pipeline.md` rule | Add programmatic path as alternative to `build-flow-designer` |
| Ref-tag version bump in any reference doc | Rules file that cites it (if ref-tag format changed) |
| `configure-scripted-agent` skill steps | `ai-agent-studio-scripted.md` (platform details must match); `scripted-agent-build.md` (build steps must match) |
| `design-scripted-agent` skill interview/output | `scripted-agent-design.md` (design methodology must match); `ai-agent-design-doc.md` Section 4d (template format must match) |
| `configure-scripted-agent` deployment steps | `configure-ai-agent` deployment steps (CCAI Config creation is shared) |
| AI Agent design doc template Section 4d | `design-scripted-agent` (produces it), `configure-scripted-agent` (consumes it), `build-scripted-fulfillment` (consumes fulfillment plan from it) |
| Import JSON schema in `ai-agent-studio-import-json.md` | `docs/templates/ai-agent-studio-import-template.json` (field set must match) and `configure-ai-agent` Step 13 procedure |
| `configure-ai-agent` Step 13 (import JSON generator) | `ai-agent-studio-import-json.md` schema and the template JSON (must stay consistent) |
