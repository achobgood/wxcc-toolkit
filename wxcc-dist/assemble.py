#!/usr/bin/env python3
"""Assemble the shippable Claude Code playbook into src/wxcc_flow/_playbook/.

"Package it" script. Enumerates TRACKED sources via `git ls-files` (never the
raw filesystem), substitutes the curated settings.bundled.json for the live
.claude/settings.json, writes the sanitized mcp.bundled.json as .mcp.json
(the live .mcp.json holds a real Supabase token and is never shipped),
preserves the repo-relative layout, then runs the link-audit gate: any residual
repo-only token fails the run.

    src/wxcc_flow/_playbook/ is GENERATED — never hand-edit it. Re-run this
    script (`python wxcc-dist/assemble.py`) after changing any shipped source.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = REPO_ROOT / "src" / "wxcc_flow" / "_playbook"
DIST_DIR = Path(__file__).resolve().parent
CURATED_SETTINGS = DIST_DIR / "settings.bundled.json"
CURATED_MCP = DIST_DIR / "mcp.bundled.json"

# Enumerate the three .claude subdirs explicitly — `.claude/` wholesale would
# also sweep the live settings.local.json and .wxcc-manifest.json that must not
# ship. .mcp.json is deliberately excluded here (the live copy holds a secret);
# the sanitized mcp.bundled.json is written in its place.
INCLUDE_PATHS = [
    "CLAUDE.md",
    ".claude/agents",
    ".claude/skills",
    ".claude/rules",
    "docs/reference",
    "docs/templates",
    "docs/playbooks",
    "docs/examples",
]
EXCLUDE_FILES: set[str] = set()
EXCLUDE_BASENAMES = {".DS_Store"}
# Tokens that only make sense in the dev repo and would leak / dangle in a
# customer folder. Bare "src/" is intentionally NOT audited: its sole shipped
# occurrence is the legitimate `src/wxcc_flow/` File Map row in CLAUDE.md that
# documents the installed CLI. All tokens below are 0-hit today and stand as
# regression guards.
AUDIT_TOKENS = ("/Users/", "venv/", ".worktrees", ".superpowers", "node_modules/", "tools/")


def enumerate_sources(repo_root: Path) -> list[str]:
    """Tracked playbook files minus explicit excludes.

    git ls-files already omits untracked/gitignored dev-only content
    (settings.local.json, .env*, .worktrees/, the .zip, __pycache__).
    """
    out = subprocess.run(
        ["git", "ls-files", "--", *INCLUDE_PATHS],
        cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout
    return [
        f for f in out.splitlines()
        if f and f not in EXCLUDE_FILES and Path(f).name not in EXCLUDE_BASENAMES
    ]


def assemble(repo_root: Path, bundle_dir: Path,
             curated_settings: Path, curated_mcp: Path) -> list[str]:
    """Wipe bundle_dir, copy sources preserving layout, substitute settings + mcp."""
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    files = enumerate_sources(repo_root)
    for rel in files:
        dest = bundle_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / rel, dest)
    settings_dest = bundle_dir / ".claude" / "settings.json"
    settings_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(curated_settings, settings_dest)
    shutil.copy2(curated_mcp, bundle_dir / ".mcp.json")
    return files


def _body_start(rel: str, lines: list[str]) -> int:
    """Rules frontmatter is exempt: its paths: globs (src/...) are Claude Code
    activation metadata — inert in a customer folder, not broken references."""
    if rel.startswith(".claude/rules/") and lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i + 1
    return 0


def audit_bundle(bundle_dir: Path) -> list[tuple[str, int, str]]:
    """Every (relpath, lineno, token) repo-only reference left in the bundle."""
    violations: list[tuple[str, int, str]] = []
    for path in sorted(bundle_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(bundle_dir).as_posix()
        lines = path.read_text(errors="replace").splitlines()
        for i in range(_body_start(rel, lines), len(lines)):
            for tok in AUDIT_TOKENS:
                if tok in lines[i]:
                    violations.append((rel, i + 1, tok))
    return violations


def main() -> int:
    files = assemble(REPO_ROOT, BUNDLE_DIR, CURATED_SETTINGS, CURATED_MCP)
    violations = audit_bundle(BUNDLE_DIR)
    if violations:
        for rel, lineno, tok in violations:
            print(f"LINK-AUDIT {rel}:{lineno}: residual '{tok}'", file=sys.stderr)
        print(f"FAILED: {len(violations)} repo-only reference(s) in the bundle.",
              file=sys.stderr)
        return 1
    print(f"Assembled {len(files) + 2} files into "
          f"{BUNDLE_DIR.relative_to(REPO_ROOT)} (incl. curated settings.json + .mcp.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
