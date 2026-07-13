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

This materializes **both** the Claude Code and Codex CLI profiles into
`my-wxcc-project/` by default (pass `--claude-only` or `--codex-only` to
install just one — see "Using with OpenAI Codex CLI" below):

```
my-wxcc-project/
├── CLAUDE.md                  # project instructions Claude Code loads at session start
├── AGENTS.md                  # project instructions Codex CLI loads
├── .mcp.json                  # Claude MCP server config (optional — see "Configure MCP servers" below)
├── .claude/
│   ├── settings.json          # pre-approved Skills, MCP tools, and wxcc-flow CLI
│   ├── agents/                # the wxcc-agent-builder agent
│   ├── skills/                # 14 build/design skills
│   └── rules/                 # platform-accuracy doc-lookup rules
├── .codex/
│   ├── config.toml            # approval policy, sandbox mode, MCP servers
│   ├── agents/                # per-agent Codex config
│   └── docs/                  # CLI command reference, doc-lookup rules
├── .agents/
│   └── skills/                # the same 14 skills, in Codex's skill format
└── docs/
    ├── reference/             # platform knowledge (Flow Designer, Connect, AI Agent Studio, …)
    ├── playbooks/             # step-by-step platform guides
    ├── templates/             # design-doc + import-JSON templates
    └── examples/              # working FlowIR / config examples
```

`init` writes a manifest per installed profile (`.claude/.wxcc-manifest.json`
and/or `.codex/.wxcc-manifest.json`) recording every file it owns. It never
overwrites files you create. If the target folder already contains files the
playbook would overwrite, `init` stops and lists them — re-run with `--force`
to overwrite, or pick an empty folder.

## Configure the `wxcc-flow` CLI (recommended)

The `wxcc-flow` CLI is the preferred way to work with Flow Designer in this
toolkit — 65 commands over the live 91-operation contract, pre-approved to run
without permission prompts in the playbook's `.claude/settings.json`.

```bash
wxcc-flow configure
```

`configure` prompts for a Webex access token (generate a personal token at
https://developer.webex.com — Getting Started → copy your token), then
auto-resolves your org ID; the project ID resolves itself on first use.
Developer-portal tokens expire after ~12 hours — re-run `configure` (or set
`WXCC_FLOW_TOKEN`) when commands return a 401. The default endpoint is US-1
production; if your WxCC org is homed in a different region, pass your region's
Flow Store base URL via `wxcc-flow configure --base-url URL`.

## Configure MCP servers (optional)

Edit `.mcp.json` in your project folder and replace the placeholders. If you
don't use one of these servers, remove its entry from `.mcp.json`.

### Supabase (if you use Supabase as your database)
- `YOUR_SUPABASE_PROJECT_REF` — your Supabase project reference ID (Project Settings → General)
- `YOUR_SUPABASE_ACCESS_TOKEN` — generate at https://supabase.com/dashboard/account/tokens

### Flow Store (`wxcc-flow-builder` MCP — Cisco's official Flow Designer MCP server)

An alternative to the `wxcc-flow` CLI for Flow Designer work — this toolkit
prefers the CLI, but Cisco's MCP server remains fully supported if you'd rather
use it.

- `YOUR_FLOW_STORE_TOKEN` — a Webex access token valid for your WxCC org. Generate a
  personal token at https://developer.webex.com (Getting Started → copy your token).
  Developer-portal tokens expire after ~12 hours; refresh and update `.mcp.json`
  when the server returns a 401.
- The bundled URL (`https://flow-store.produs1.ciscoccservice.com/flow-store/mcp`)
  is the **US-1 production** endpoint. Use production endpoints only; if your WxCC
  org is homed in a different region, replace the host with your region's
  production Flow Store URL.

## Start building

Open the folder in Claude Code and start a fresh session:

```bash
cd my-wxcc-project
claude
```

Then run `/wxcc-agent-builder` to build an agent, or `/wxcc-debug` to troubleshoot
a failing action. The builder walks you through everything — from database setup
through a working AI agent handling calls.

## Using with OpenAI Codex CLI

The playbook ships both assistant profiles side by side. `wxcc-flow init`
writes Claude Code files (`CLAUDE.md`, `.claude/`) and Codex files
(`AGENTS.md`, `.codex/`, `.agents/skills/`) into the same folder — use
`--claude-only` or `--codex-only` to restrict it:

    pip install wxcc-toolkit
    wxcc-flow init my-wxcc-project
    cd my-wxcc-project
    codex

Trust the folder when Codex prompts — the shipped `.codex/config.toml`
(approval policy, sandbox mode, MCP servers) only takes effect in a trusted
folder. `AGENTS.md` and the skills under `.agents/skills/` load automatically;
the CLI command reference lives in `.codex/docs/cli-commands.md`.

**MCP servers (Flow Store token).** Unlike Claude Code, the Codex Flow Store
MCP server reads its token from an environment variable, not from a file — the
generated `.codex/config.toml` sets `bearer_token_env_var = "WXCC_FLOW_TOKEN"`.
Export that variable (it is the same one `wxcc-flow` itself reads) so no token
is ever written into a project file:

    export WXCC_FLOW_TOKEN="your-webex-token"

`wxcc-flow configure` (used for the CLI) does NOT set this — export the env var
yourself. If you also use the Supabase MCP server, replace the
`YOUR_SUPABASE_ACCESS_TOKEN` / `YOUR_SUPABASE_PROJECT_REF` placeholders in
`.codex/config.toml`.

The Codex profile is generated from the Claude profile at build time — the
two never drift. Codex has no per-command allowlist, so expect an approval
prompt when a command needs to run outside the workspace sandbox.

## Staying up to date

`pip` never upgrades on its own, so `wxcc-flow` checks PyPI once a day (a
best-effort call with a 1-second timeout, cached in `~/.wxcc-flow/`) and, when a
newer release exists, prints one line to stderr before the command runs:

> wxcc-flow 0.3.4 available (you have 0.3.3). Upgrade: pip install -U wxcc-toolkit && wxcc-flow init

Both steps matter: `pip install -U wxcc-toolkit` updates the CLI, and
`wxcc-flow init` (see below) refreshes the playbook files in your project folder.
The check never blocks a command and stays silent on any network error. Silence
it with the `--no-update-check` flag, by setting `WXCC_FLOW_NO_UPDATE_CHECK=1`,
or in CI (it is skipped automatically when `CI` is set).

## Update an existing project folder

After upgrading the package (`pip install --upgrade wxcc-toolkit`), refresh a
project folder to the new playbook version:

```bash
wxcc-toolkit init my-wxcc-project --force
```

This automatically refreshes **only the profiles already installed** in that
folder — a Claude-only folder stays Claude-only, a Codex-only folder stays
Codex-only, and a dual-profile folder refreshes both. `--force` touches only
manifest-owned files (retired skills are removed, updated docs are rewritten)
and leaves any files you added untouched.

To **add** the other profile to an existing folder, pass its flag —
`wxcc-toolkit init my-wxcc-project --codex-only` (or `--claude-only`).

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
