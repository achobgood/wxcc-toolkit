<!-- @section: ## Quick Start -->
## Quick Start

Ask Codex to use the **wxcc-agent-builder** agent (defined in
`.codex/agents/wxcc-agent-builder.toml`) to start building an agent. It will
walk you through everything — from database setup through a working AI agent
handling calls.

<!-- @section: ## Agent Invocation Rules -->
## Agent Invocation Rules

Codex orchestrates subagents itself — it spawns them, routes follow-up
instructions, waits for results, and closes agent threads. Ask Codex to use
the **wxcc-agent-builder** agent for the full workflow (interview, design,
build). Refine conversationally with follow-up instructions in the same
session — do NOT restart the agent per question.

<!-- @section: ## If Debugging -->
## If Debugging

Use the `wxcc-debug` skill to troubleshoot a failing action.

<!-- @section: ### Skill Invocation Rule -->
### Skill Invocation Rule

When the agent or a skill says "YOU MUST use skill X" or "Step 1: Load
references — read these docs," that is not a suggestion. The reference docs
contain platform-specific conventions that CANNOT be guessed correctly from
training data — this applies to Connect node wiring, Flow Designer activities,
AI Agent Studio configuration, Control Hub setup, and all outbound/inbound
flow patterns alike.

If you skip the skill or skip reading the reference docs, the output WILL
contain invented details that don't match the actual platform behavior.

Per-topic lookup procedures (mandatory lookup sequences, citation format,
ref-tag proof-of-read) live in `.codex/docs/rules/` — read the file matching
the question's topic BEFORE answering any platform question. These are
reference procedure docs; Codex does not load them automatically.

<!-- @section: ### Pre-approved in Claude Code -->
### Approvals in Codex

Codex has no per-command allowlist equivalent to `Bash(wxcc-flow:*)`.
This folder ships `.codex/config.toml` with `approval_policy = "on-request"`
and `sandbox_mode = "workspace-write"`; both take effect ONLY after you trust
the folder in Codex. Expect an approval prompt when a command must run
outside the sandbox.

<!-- @section: ### Key Commands -->
### Key Commands

The full command reference table (all commands, one row each) lives in
`.codex/docs/cli-commands.md`. `wxcc-flow --help` and
`wxcc-flow <command> --help` give the same facts from the CLI itself.

<!-- @section: ### Known CLI Limitations -->
### Known CLI Limitations

The full known-limitations table (per-command gotchas and their workarounds)
lives in `.codex/docs/cli-limitations.md`. Consult it before relying on any
`wxcc-flow` command's edge-case behavior.

<!-- @section: ## Sync Checklist (Preventing Config Drift) -->
## Sync Checklist (Preventing Config Drift)

Maintainer checklist for keeping shared doc sections in sync — the full table
lives in `.codex/docs/sync-checklist.md`. Consult it before editing any
reference doc or skill in this folder.
