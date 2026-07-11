# WxCC AI Agent Builder Toolkit (`wxcc-toolkit`)

Build AI agents and voice flows for Webex Contact Center with guided Claude Code
assistance. This package delivers the **entire Claude Code playbook** — the
`wxcc-agent-builder` agent, all 14 skills, all doc-lookup rules, and the full
platform reference/playbook/template library — plus the `wxcc-flow` Flow Designer
CLI, and materializes them into a working folder with one command.

## Install

```bash
pip install wxcc-toolkit
```

This installs two console commands (aliases of the same CLI): `wxcc-toolkit` and
`wxcc-flow`.

## Create a project folder

```bash
wxcc-toolkit init my-wxcc-project
```

This materializes the playbook into `my-wxcc-project/`:

```
my-wxcc-project/
├── CLAUDE.md                  # project instructions Claude Code loads at session start
├── .mcp.json                  # MCP server config (placeholders — fill in step below)
├── .claude/
│   ├── settings.json          # pre-approved Skills, MCP tools, and wxcc-flow CLI
│   ├── agents/                # the wxcc-agent-builder agent
│   ├── skills/                # 14 build/design skills
│   └── rules/                 # platform-accuracy doc-lookup rules
└── docs/
    ├── reference/             # platform knowledge (Flow Designer, Connect, AI Agent Studio, …)
    ├── playbooks/             # step-by-step platform guides
    ├── templates/             # design-doc + import-JSON templates
    └── examples/              # working FlowIR / config examples
```

`init` writes a manifest (`.claude/.wxcc-manifest.json`) recording every file it
owns. It never overwrites files you create. If the target folder already contains
files the playbook would overwrite, `init` stops and lists them — re-run with
`--force` to overwrite, or pick an empty folder.

## Configure MCP servers

Edit `.mcp.json` in your project folder and replace the placeholders:

### Supabase (if you use Supabase as your database)
- `YOUR_SUPABASE_PROJECT_REF` — your Supabase project reference ID (Project Settings → General)
- `YOUR_SUPABASE_ACCESS_TOKEN` — generate at https://supabase.com/dashboard/account/tokens

### Flow Store (`wxcc-flow-builder` MCP — WxCC Flow Designer)
- `YOUR_FLOW_STORE_TOKEN` — a Webex access token valid for your WxCC org. Generate a
  personal token at https://developer.webex.com (Getting Started → copy your token).
  The endpoint is `https://flow-store.produs1.ciscoccservice.com/flow-store/mcp`.
  Developer-portal tokens expire after ~12 hours; refresh and update `.mcp.json`
  when the server returns a 401.

If you don't use one of these backends, remove its entry from `.mcp.json`.

## Start building

Open the folder in Claude Code and start a fresh session:

```bash
cd my-wxcc-project
claude
```

Then run `/wxcc-agent-builder` to build an agent, or `/wxcc-debug` to troubleshoot
a failing action. The builder walks you through everything — from database setup
through a working AI agent handling calls.

## Update an existing project folder

After upgrading the package (`pip install --upgrade wxcc-toolkit`), refresh a
project folder to the new playbook version:

```bash
wxcc-toolkit init my-wxcc-project --force
```

`--force` refreshes only manifest-owned files (retired skills are removed, updated
docs are rewritten) and leaves any files you added untouched.

## Remove the playbook from a folder

```bash
wxcc-toolkit init my-wxcc-project --uninstall
```

Deletes every manifest-owned file and the manifest itself. Files you created are
left in place.

## For maintainers

`src/wxcc_flow/_playbook/` is **generated** — never hand-edit it. After changing any
shipped source (`CLAUDE.md`, `.claude/agents|skills|rules`, `docs/reference|templates|playbooks|examples`),
regenerate the bundle:

```bash
python wxcc-dist/assemble.py
```

`assemble.py` enumerates tracked sources via `git ls-files`, substitutes the curated
`wxcc-dist/settings.bundled.json` and sanitized `wxcc-dist/mcp.bundled.json`, and runs a
link-audit gate that fails on residual dev-only paths. The release workflow re-runs it and
refuses to publish if the committed bundle is stale.
