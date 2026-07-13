"""Tests for `wxcc-toolkit init` (src/wxcc_flow/init_playbook.py).

Invokes the real command surface on the main Typer app so registration in
main.py is exercised too. bundle_root() is monkeypatched to a fake installed
bundle so tests never depend on the generated src/wxcc_flow/_playbook/.
"""
import json

import pytest
from typer.testing import CliRunner

import wxcc_flow.init_playbook as I
from wxcc_flow.main import app

runner = CliRunner()
MANIFEST = ".claude/.wxcc-manifest.json"


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    """Fake installed _playbook/ (incl. hidden .mcp.json + .claude/) + patched bundle_root()."""
    b = tmp_path / "_playbook"
    for rel, text in {
        "CLAUDE.md": "# Playbook\n",
        ".mcp.json": '{"mcpServers": {}}\n',
        ".claude/settings.json": '{"permissions": {"allow": ["Bash(wxcc-flow:*)"]}}',
        ".claude/agents/wxcc-agent-builder.md": "agent\n",
        ".claude/skills/design-flow/SKILL.md": "skill v1\n",
        "docs/reference/flow-designer-essentials.md": "ref\n",
        "docs/playbooks/wxcc-setup.md": "playbook\n",
    }.items():
        p = b / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    monkeypatch.setattr(I, "bundle_root", lambda: b)
    return b


def _init(*args):
    return runner.invoke(app, ["init", *args])


def _registered_opts(cmd_name):
    """Flags registered on a top-level command — robust to typer/rich help
    rendering, which colorizes flag text and can break literal substring matches
    on newer typer/rich versions."""
    import typer
    click_app = typer.main.get_command(app)
    return {opt for p in click_app.commands[cmd_name].params for opt in p.opts}


def test_init_command_registered_on_main_app():
    """The flat registration in main.py exposes `init` with its flags."""
    r = runner.invoke(app, ["init", "--help"])
    assert r.exit_code == 0, r.output
    opts = _registered_opts("init")
    assert "--uninstall" in opts and "--force" in opts


def test_fresh_init_writes_tree_and_manifest(bundle, tmp_path):
    pb = tmp_path / "pb"
    r = _init(str(pb), "--yes")
    assert r.exit_code == 0, r.output
    # layout mirrors the repo → references resolve from folder root
    assert (pb / "CLAUDE.md").exists()
    assert (pb / ".mcp.json").exists()                       # hidden bundle-root file lands
    assert (pb / "docs/playbooks/wxcc-setup.md").exists()    # playbooks included
    m = json.loads((pb / MANIFEST).read_text())
    assert m["wxcc_playbook"] is True and "version" in m
    assert set(m["files"]) == {
        "CLAUDE.md", ".mcp.json", ".claude/settings.json",
        ".claude/agents/wxcc-agent-builder.md",
        ".claude/skills/design-flow/SKILL.md",
        "docs/reference/flow-designer-essentials.md",
        "docs/playbooks/wxcc-setup.md",
    }
    assert "fresh session" in r.output


def test_first_init_into_nonempty_folder_aborts_with_collision_list(bundle, tmp_path):
    pb = tmp_path / "pb"
    (pb / "CLAUDE.md").parent.mkdir(parents=True)
    (pb / "CLAUDE.md").write_text("the user's own file\n")
    r = _init(str(pb))
    assert r.exit_code == 1
    assert "CLAUDE.md" in r.output                            # names the colliding path
    assert (pb / "CLAUDE.md").read_text() == "the user's own file\n"  # untouched


def test_first_init_force_overwrites_collisions(bundle, tmp_path):
    pb = tmp_path / "pb"
    pb.mkdir()
    (pb / "CLAUDE.md").write_text("old\n")
    r = _init(str(pb), "--force")
    assert r.exit_code == 0, r.output
    assert (pb / "CLAUDE.md").read_text() == "# Playbook\n"


def test_user_file_survives_force_refresh_and_uninstall(bundle, tmp_path):
    """Required manifest-ownership guarantee: a user-created file is untouched by
    BOTH `init --force` (refresh) and `--uninstall`; owned files refresh/retire."""
    pb = tmp_path / "pb"
    assert _init(str(pb), "--yes").exit_code == 0
    (pb / "my-notes.md").write_text("mine\n")                # user-added, unowned
    (pb / "CLAUDE.md").write_text("locally edited\n")        # owned, drifted

    # new bundle version: a skill retired, CLAUDE.md changed
    (bundle / "CLAUDE.md").write_text("# Playbook v2\n")
    (bundle / ".claude/skills/design-flow/SKILL.md").unlink()

    r = _init(str(pb), "--force")                            # refresh
    assert r.exit_code == 0, r.output
    assert (pb / "CLAUDE.md").read_text() == "# Playbook v2\n"        # owned → refreshed
    assert not (pb / ".claude/skills/design-flow/SKILL.md").exists()  # retired → removed
    assert (pb / "my-notes.md").read_text() == "mine\n"              # unowned → survives --force

    r = _init(str(pb), "--uninstall")
    assert r.exit_code == 0, r.output
    assert not (pb / "CLAUDE.md").exists()                           # owned → removed
    assert not (pb / MANIFEST).exists()
    assert (pb / "my-notes.md").read_text() == "mine\n"             # unowned → survives --uninstall


def test_uninstall_without_manifest_errors(bundle, tmp_path):
    pb = tmp_path / "pb"
    pb.mkdir()
    assert _init(str(pb), "--uninstall").exit_code == 1
