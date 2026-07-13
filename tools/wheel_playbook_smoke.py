#!/usr/bin/env python3
"""Verify that a built wxcc-toolkit wheel ships a usable Claude/Codex playbook.

Intentionally stdlib-only. Installs the wheel into a fresh venv and runs the
installed `wxcc-flow init` from a temp directory, so success cannot come from
the checkout, an editable install, or PYTHONPATH.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

GROUNDING_MARKER = "NEVER answer questions about any Cisco platform from training data"
SHARED_DOCS = (
    "docs/reference/flow-designer-essentials.md",
    "docs/reference/webex-connect.md",
    "docs/playbooks/wxcc-setup.md",
    "docs/templates/ai-agent-design-doc.md",
)
CLAUDE_DIRS = (".claude/agents", ".claude/skills", ".claude/rules")
CODEX_DIRS = (".codex/agents", ".codex/docs/rules", ".agents/skills")
SANITIZED = (
    (".mcp.json", "YOUR_SUPABASE_PROJECT_REF"),
    (".codex/config.toml", "WXCC_FLOW_TOKEN"),   # Flow Store auth is env-backed, no token in-file
)


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _assert_exists(root: Path, relative_paths: tuple[str, ...]) -> None:
    missing = [rel for rel in relative_paths if not (root / rel).exists()]
    if missing:
        raise AssertionError(f"{root} is missing: {', '.join(missing)}")


def _assert_populated_directory(root: Path, relative_path: str) -> None:
    d = root / relative_path
    if not d.is_dir() or not any(p.is_file() for p in d.rglob("*")):
        raise AssertionError(f"{root} is missing populated {relative_path}/")


def _assert_manifest(root: Path, profile: str) -> None:
    path = root / f".{profile}/.wxcc-manifest.json"
    manifest = json.loads(path.read_text())
    if manifest.get("wxcc_playbook") is not True or manifest.get("profile") != profile:
        raise AssertionError(f"unexpected {profile} manifest at {path}: {manifest!r}")
    if not isinstance(manifest.get("files"), dict) or not manifest["files"]:
        raise AssertionError(f"{profile} manifest has no owned files: {path}")


def _assert_forbidden(root: Path, names: tuple[str, ...], profile: str) -> None:
    for name in names:
        if (root / name).exists():
            raise AssertionError(f"{profile} profile unexpectedly contains {name}")


def _assert_claude(root: Path) -> None:
    _assert_exists(root, ("CLAUDE.md", ".mcp.json") + SHARED_DOCS)
    for rel in CLAUDE_DIRS:
        _assert_populated_directory(root, rel)
    _assert_manifest(root, "claude")


def _assert_codex(root: Path) -> None:
    _assert_exists(root, ("AGENTS.md", ".codex/config.toml",
                          ".codex/docs/cli-commands.md",
                          ".codex/docs/sync-checklist.md") + SHARED_DOCS)
    for rel in CODEX_DIRS:
        _assert_populated_directory(root, rel)
    _assert_manifest(root, "codex")
    with (root / ".codex/config.toml").open("rb") as fh:
        cfg = tomllib.load(fh)
    if "mcp_servers" not in cfg or cfg.get("approval_policy") != "on-request":
        raise AssertionError("generated .codex/config.toml lost approval or mcp_servers")
    for path in sorted((root / ".codex/agents").glob("*.toml")):
        with path.open("rb") as fh:
            tomllib.load(fh)
    agents_md = root / "AGENTS.md"
    if GROUNDING_MARKER not in agents_md.read_text():
        raise AssertionError("generated AGENTS.md lost the mandatory grounding rule")
    if agents_md.stat().st_size > 32768:
        raise AssertionError("installed AGENTS.md exceeds the 32768-byte Codex cap")


def _assert_sanitized(root: Path) -> None:
    for rel, placeholder in SANITIZED:
        p = root / rel
        if p.exists() and placeholder not in p.read_text():
            raise AssertionError(f"{rel} shipped without its sanitized placeholder")


def _wheel_from(path: Path) -> Path:
    if path.is_file() and path.suffix == ".whl":
        return path.resolve()
    wheels = sorted(path.glob("wxcc_toolkit-*.whl")) if path.is_dir() else []
    if len(wheels) != 1:
        raise AssertionError(f"expected one wxcc_toolkit wheel in {path}, found {wheels}")
    return wheels[0].resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, help="built wheel (or a directory containing one)")
    args = parser.parse_args()
    wheel = _wheel_from(args.wheel)

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="wxcc-wheel-smoke-") as temp:
        root = Path(temp)
        venv = root / "venv"
        _run([sys.executable, "-m", "venv", str(venv)], cwd=root, env=env)
        bindir = "Scripts" if os.name == "nt" else "bin"
        python = venv / bindir / ("python.exe" if os.name == "nt" else "python")
        wxcc = venv / bindir / ("wxcc-flow.exe" if os.name == "nt" else "wxcc-flow")
        _run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
              str(wheel)], cwd=root, env=env)

        claude, codex, both = root / "claude", root / "codex", root / "both"
        _run([str(wxcc), "init", str(claude), "--claude-only", "--yes"], cwd=root, env=env)
        _run([str(wxcc), "init", str(codex), "--codex-only", "--yes"], cwd=root, env=env)
        _run([str(wxcc), "init", str(both), "--yes"], cwd=root, env=env)

        _assert_claude(claude)
        _assert_forbidden(claude, ("AGENTS.md", ".codex", ".agents"), "claude-only")
        _assert_codex(codex)
        _assert_forbidden(codex, ("CLAUDE.md", ".claude", ".mcp.json"), "codex-only")
        _assert_claude(both)
        _assert_codex(both)
        for folder in (claude, codex, both):
            _assert_sanitized(folder)
    print("Wheel playbook smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
