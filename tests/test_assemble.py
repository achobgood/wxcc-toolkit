"""Tests for wxcc-dist/assemble.py — enumeration scope, curated substitution,
the link-audit gate, and byte-identical idempotency."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "assemble", REPO_ROOT / "wxcc-dist" / "assemble.py"
)


def _load_assemble():
    mod = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(mod)
    return mod


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _tree_digest(root):
    return [
        (p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(root.rglob("*")) if p.is_file()
    ]


def test_curated_configs_are_customer_safe():
    dist = REPO_ROOT / "wxcc-dist"
    settings = json.loads((dist / "settings.bundled.json").read_text())
    allow = settings["permissions"]["allow"]
    assert "Bash(wxcc-flow:*)" in allow and "Bash(wxcc-toolkit:*)" in allow
    assert sum(1 for a in allow if a.startswith("Skill(")) == 14      # all skills pre-approved
    assert settings["enabledMcpjsonServers"] == ["supabase", "wxcc-flow-builder"]

    raw = (dist / "mcp.bundled.json").read_text()
    mcp = json.loads(raw)
    assert set(mcp["mcpServers"]) == {"supabase", "wxcc-flow-builder"}
    assert "YOUR_SUPABASE_ACCESS_TOKEN" in raw and "YOUR_FLOW_STORE_TOKEN" in raw
    assert "sbp_" not in raw                                          # no live token ships


@pytest.fixture
def fake_repo(tmp_path):
    """Mini repo mirroring the real tree's shipping/dev split."""
    repo = tmp_path / "repo"
    tracked = {
        "CLAUDE.md": "# Playbook\n",
        ".claude/agents/wxcc-agent-builder.md": "agent\n",
        ".claude/skills/design-flow/SKILL.md": "skill\n",
        ".claude/skills/build-action/references/notes.md": "nested\n",
        ".claude/settings.json": '{"hooks": {"SessionStart": []}}',
        "docs/reference/flow-designer-essentials.md": "ref\n",
        "docs/reference/.DS_Store": "junk\n",
        "docs/playbooks/wxcc-setup.md": "playbook\n",
        "docs/templates/design-doc.md": "template\n",
        "docs/examples/simple.json": "{}\n",
        "src/wxcc_flow/main.py": "app\n",
    }
    for rel, content in tracked.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    # untracked / gitignored dev junk that must never ship
    (repo / ".claude/settings.local.json").write_text("{}")
    (repo / ".mcp.json").write_text('{"mcpServers": {"supabase": {"env": {"SUPABASE_ACCESS_TOKEN": "sbp_LIVE"}}}}')
    _git(repo, "init", "-q")
    _git(repo, "add", "-f", *tracked)
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x")
    return repo


def test_enumeration_scopes_and_excludes(fake_repo):
    A = _load_assemble()
    files = A.enumerate_sources(fake_repo)
    assert "CLAUDE.md" in files
    assert ".claude/skills/build-action/references/notes.md" in files  # nested layout kept
    assert "docs/playbooks/wxcc-setup.md" in files                     # playbooks included
    assert "docs/examples/simple.json" in files                        # examples included
    assert "docs/reference/.DS_Store" not in files                     # basename exclude
    assert ".claude/settings.local.json" not in files                 # untracked
    assert ".claude/settings.json" not in files                       # substituted, not enumerated
    assert ".mcp.json" not in files                                   # live secret, never enumerated
    assert "src/wxcc_flow/main.py" not in files                       # outside include scope


def test_assemble_substitutes_settings_and_mcp(fake_repo, tmp_path):
    A = _load_assemble()
    curated_s = tmp_path / "s.json"
    curated_s.write_text('{"permissions": {"allow": ["Bash(wxcc-flow:*)"]}}')
    curated_m = tmp_path / "m.json"
    curated_m.write_text('{"mcpServers": {"supabase": {"env": {"SUPABASE_ACCESS_TOKEN": "YOUR_SUPABASE_ACCESS_TOKEN"}}}}')
    bundle = tmp_path / "bundle"
    A.assemble(fake_repo, bundle, curated_s, curated_m)
    assert (bundle / "CLAUDE.md").read_text() == "# Playbook\n"
    assert (bundle / ".claude/skills/build-action/references/notes.md").exists()
    shipped = json.loads((bundle / ".claude/settings.json").read_text())
    assert "hooks" not in shipped                                     # live settings NOT shipped
    mcp = (bundle / ".mcp.json").read_text()
    assert "YOUR_SUPABASE_ACCESS_TOKEN" in mcp and "sbp_LIVE" not in mcp  # sanitized mcp shipped
    assert not (bundle / "docs/reference/.DS_Store").exists()


def test_assemble_is_idempotent_byte_identical(fake_repo, tmp_path):
    A = _load_assemble()
    curated_s = tmp_path / "s.json"
    curated_s.write_text('{"permissions": {"allow": []}}')
    curated_m = tmp_path / "m.json"
    curated_m.write_text('{"mcpServers": {}}')
    bundle = tmp_path / "bundle"
    A.assemble(fake_repo, bundle, curated_s, curated_m)
    first = _tree_digest(bundle)
    A.assemble(fake_repo, bundle, curated_s, curated_m)
    second = _tree_digest(bundle)
    assert first == second and len(first) > 0


def test_audit_flags_planted_tokens_with_path_and_line(tmp_path):
    A = _load_assemble()
    bundle = tmp_path / "b"
    (bundle / "docs").mkdir(parents=True)
    (bundle / "docs/x.md").write_text(
        "clean line\n"
        "see /Users/dev/secret\n"
        "activate venv/bin\n"
        "cd node_modules/pkg\n"
        "edit tools/gen.py\n"
    )
    got = A.audit_bundle(bundle)
    assert ("docs/x.md", 2, "/Users/") in got
    assert ("docs/x.md", 3, "venv/") in got
    assert ("docs/x.md", 4, "node_modules/") in got
    assert ("docs/x.md", 5, "tools/") in got


def test_audit_passes_clean_bundle(tmp_path):
    A = _load_assemble()
    bundle = tmp_path / "b"
    bundle.mkdir()
    # legitimate `src/wxcc_flow/` File Map row must NOT trip the gate
    (bundle / "CLAUDE.md").write_text("| `src/wxcc_flow/` | the CLI package |\n")
    assert A.audit_bundle(bundle) == []


def test_audit_exempts_rules_frontmatter_but_not_body(tmp_path):
    A = _load_assemble()
    bundle = tmp_path / "b"
    (bundle / ".claude/rules").mkdir(parents=True)
    (bundle / ".claude/rules/x.md").write_text(
        '---\npaths:\n  - "tools/x.py"\n---\n\nbody tools/ ref\n'
    )
    got = A.audit_bundle(bundle)
    assert (".claude/rules/x.md", 6, "tools/") in got                 # body still audited
    assert not any(ln == 3 for _, ln, _ in got)                       # frontmatter glob exempt


# ── Codex transform: phrase map ──────────────────────────────────────────

def test_phrase_map_rewrites_prose_slash_commands_not_paths():
    A = _load_assemble()
    out = A.apply_phrase_map(
        "Run `/wxcc-agent-builder` to start. Run `/wxcc-debug` to debug.\n"
        "| `.claude/skills/wxcc-debug/` | Skill: debug failing actions |\n"
    )
    assert "/wxcc-agent-builder" not in out
    assert "wxcc-agent-builder** agent" in out
    assert ".agents/skills/wxcc-debug/" in out          # path segment survived intact
    assert "the `wxcc-debug` skill" in out


def test_phrase_map_path_swaps_most_specific_first():
    A = _load_assemble()
    out = A.apply_phrase_map(
        ".claude/agents/wxcc-agent-builder.md and .claude/settings.json "
        "and .claude/rules/bre-questions.md and .claude/anythingelse"
    )
    assert ".codex/agents/wxcc-agent-builder.toml" in out
    assert ".codex/config.toml" in out
    assert ".codex/docs/rules/bre-questions.md" in out
    assert ".codex/anythingelse" in out                  # generic catch-all last
    assert ".claude/" not in out


def test_phrase_map_tool_isms():
    A = _load_assemble()
    out = A.apply_phrase_map(
        "use SendMessage to continue; YOU MUST call Skill(build-action); "
        "Claude Code loads CLAUDE.md"
    )
    assert "SendMessage" not in out
    assert "Skill(build-action)" not in out
    assert "the `build-action` skill" in out
    assert "Codex loads AGENTS.md" in out


# ── Codex transform: AGENTS.md build ─────────────────────────────────────

def test_replace_sections_swaps_anchored_block_and_errors_on_miss():
    A = _load_assemble()
    md = "# T\n\n## Keep\nbody\n\n## Swap\nold\n\n### Sub\nx\n\n## After\ny\n"
    out = A.replace_sections(md, {"## Swap": "## Swapped\nnew"})
    assert "## Swapped\nnew" in out and "old" not in out
    assert "### Sub" not in out            # ### is deeper → swallowed with the ## block
    assert "## After\ny" in out
    with pytest.raises(KeyError):
        A.replace_sections(md, {"## Missing": "z"})


def test_extract_section_returns_heading_and_body():
    A = _load_assemble()
    md = "## A\na1\n\n### K\nk1\nk2\n\n### L\nl1\n\n## B\nb1\n"
    block = A.extract_section(md, "### K")
    assert block.startswith("### K\n") and "k2" in block
    assert "l1" not in block and "## B" not in block
    with pytest.raises(KeyError):
        A.extract_section(md, "### Missing")


def test_build_agents_md_real_claude_md_under_cap_with_pointers():
    A = _load_assemble()
    claude_md = (Path(A.REPO_ROOT) / "CLAUDE.md").read_text()
    agents_md, extracted = A.build_agents_md(claude_md)
    assert len(agents_md.encode("utf-8")) <= 32768
    assert A.GROUNDING_MARKER in agents_md
    assert ".codex/docs/cli-commands.md" in agents_md
    assert ".codex/docs/sync-checklist.md" in agents_md
    assert set(extracted) == {".codex/docs/cli-commands.md", ".codex/docs/sync-checklist.md"}
    # the extracted table content moved OUT of AGENTS.md and INTO the docs
    assert "| `wxcc-flow list` |" not in agents_md
    assert "| `wxcc-flow list` |" in extracted[".codex/docs/cli-commands.md"]
    assert "Sync Checklist" in extracted[".codex/docs/sync-checklist.md"]
    for content in extracted.values():
        assert "CLAUDE.md" not in content and ".claude/" not in content


def test_build_agents_md_fails_hard_when_over_cap():
    A = _load_assemble()
    claude_md = (Path(A.REPO_ROOT) / "CLAUDE.md").read_text()
    padded = ("x" * 40000) + "\n" + claude_md
    with pytest.raises(ValueError, match="32768"):
        A.build_agents_md(padded)


# ── Codex transform: agent → TOML ────────────────────────────────────────

AGENT_MD = """---
name: test-agent
description: |
  Build things. Use SendMessage to continue the "existing" agent.
tools: Read, Edit
model: opus
---
Body here. Run `/wxcc-debug` if stuck. See .claude/skills/build-action/.
"""


def test_md_agent_to_toml_fields_and_phrase_map():
    A = _load_assemble()
    tomllib = pytest.importorskip("tomllib")
    out = A.md_agent_to_toml(AGENT_MD)
    data = tomllib.loads(out)
    assert data["name"] == "test-agent"
    assert data["model_reasoning_effort"] == "high"          # opus → high
    assert data["sandbox_mode"] == "workspace-write"
    assert "model" not in data                                # inherit Codex default
    assert "SendMessage" not in data["description"]           # description phrase-mapped
    assert '"existing"' in data["description"]                # quotes escaped, survive parse
    assert "the `wxcc-debug` skill" in data["developer_instructions"]
    assert ".agents/skills/build-action/" in data["developer_instructions"]


def test_md_agent_to_toml_rejects_triple_quote_body():
    A = _load_assemble()
    bad = AGENT_MD.replace("Body here.", "Body ''' here.")
    with pytest.raises(ValueError, match="'''"):
        A.md_agent_to_toml(bad)


def test_real_agent_converts_and_parses():
    A = _load_assemble()
    tomllib = pytest.importorskip("tomllib")
    src = (Path(A.REPO_ROOT) / ".claude/agents/wxcc-agent-builder.md").read_text()
    data = tomllib.loads(A.md_agent_to_toml(src))
    assert data["name"] == "wxcc-agent-builder"
    assert data["model_reasoning_effort"] == "high"           # frontmatter says model: opus
    assert data["developer_instructions"].strip()


# ── Codex transform: MCP translation ─────────────────────────────────────

def test_mcp_servers_toml_translates_sanitized_bundle():
    A = _load_assemble()
    tomllib = pytest.importorskip("tomllib")
    frag = A._mcp_servers_toml(Path(A.DIST_DIR) / "mcp.bundled.json")
    data = tomllib.loads(frag)
    src = json.loads((Path(A.DIST_DIR) / "mcp.bundled.json").read_text())
    assert set(data["mcp_servers"]) == set(src["mcpServers"])
    sup = data["mcp_servers"]["supabase"]
    assert sup["command"] == "npx"
    assert sup["args"] == src["mcpServers"]["supabase"]["args"]
    assert sup["env"] == {"SUPABASE_ACCESS_TOKEN": "YOUR_SUPABASE_ACCESS_TOKEN"}
    fb = data["mcp_servers"]["wxcc-flow-builder"]
    assert fb["url"] == src["mcpServers"]["wxcc-flow-builder"]["url"]
    assert fb["http_headers"] == {"Authorization": "Bearer YOUR_FLOW_STORE_TOKEN"}


def test_mcp_servers_toml_rejects_unknown_shape(tmp_path):
    A = _load_assemble()
    bad = tmp_path / "mcp.json"
    bad.write_text(json.dumps({"mcpServers": {"weird": {"transport": "ws"}}}))
    with pytest.raises(ValueError, match="weird"):
        A._mcp_servers_toml(bad)
