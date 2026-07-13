---
description: Enforces the correct skill pipeline for Flow Designer voice flow builds
---

# Flow Designer Build Pipeline

When building a Flow Designer voice flow, skills must be invoked in the correct sequence. Skipping steps produces incomplete or incorrect output.

## Required Pipeline

```
design-flow → [user review] → build-spec-diagram (optional) → build-flow-designer OR build-flow-programmatic → wxcc-setup
```

1. **`design-flow`** — Translates requirements into a complete design doc (activities, connections, variables, event handlers). Saves to `docs/plans/`. The user must review and approve this before proceeding.
2. **`build-spec-diagram`** (optional) — Generates a .drawio visual diagram from the design doc. Useful for user review but not required for the build.
3. **Build the flow** (one of two paths):
   - **`build-flow-designer`** — Generates step-by-step UI build instructions from the design doc. The user manually creates each activity in the Flow Designer UI. REQUIRES a design doc.
   - **`build-flow-programmatic`** — Generates FlowIR JSON, validates via `wxcc-flow` CLI, and creates the flow programmatically. Faster but requires CLI access and a valid API token. REQUIRES a design doc.
4. **WxCC setup** — Control Hub configuration (entry point, queue, team, PSTN, flow assignment). Uses `docs/playbooks/wxcc-setup.md`.

## Hard Rules

- NEVER invoke `build-flow-designer` or `build-flow-programmatic` without a design doc in `docs/plans/`. Both skills require a design doc — without one, they cannot produce correct activity-level output.
- NEVER skip user review of the design doc. The design doc is the contract — if activities or connections are wrong, the build output will be wrong too.
- If the user asks to "build a flow" without prior design work, start with `design-flow`, not a build skill.
- If a design doc already exists in `docs/plans/`, either build skill can consume it directly — no need to re-run `design-flow`.

## Choosing Between Build Paths

- Use **`build-flow-designer`** when the user wants to learn the Flow Designer UI or needs manual control over each activity.
- Use **`build-flow-programmatic`** when the user wants fast automated flow creation via the `wxcc-flow` CLI.
- If ambiguous, ask: "Do you want step-by-step UI build instructions (manual) or programmatic flow creation via the CLI (automated)?"
