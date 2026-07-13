"""Offline doc-consistency invariants (default suite; no token needed).

These are the Task 9 "final gate": after editing docs they prove the situational
activity index still matches the files on disk and the shipped `_playbook` mirror
is byte-identical to the repo (excluding the two curated substitution files).
Kept OUT of the `live` tier so a plain `pytest` runs them with zero API calls.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ACT_DIR = REPO / "docs" / "reference" / "flow-designer-activities"
PLAYBOOK = REPO / "src" / "wxcc_flow" / "_playbook"

# Curated per-customer substitutions — intentionally NOT byte-identical to repo.
_CURATED = {".mcp.json", ".claude/settings.json"}


def _index_linked_files():
    text = (ACT_DIR / "_index.md").read_text()
    return set(re.findall(r"\]\(([a-z0-9-]+\.md)\)", text))


def test_index_rows_match_files_on_disk():
    linked = _index_linked_files()
    on_disk = {p.name for p in ACT_DIR.glob("*.md") if p.name != "_index.md"}
    missing_file = sorted(linked - on_disk)
    unlisted = sorted(on_disk - linked)
    assert not missing_file, f"_index.md links files that do not exist: {missing_file}"
    assert not unlisted, f"activity files not listed in _index.md: {unlisted}"


def test_playbook_mirror_is_byte_identical():
    drift, missing = [], []
    for p in PLAYBOOK.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(PLAYBOOK).as_posix()
        if rel in _CURATED:
            continue
        repo_file = REPO / rel
        if not repo_file.exists():
            missing.append(rel)
        elif repo_file.read_bytes() != p.read_bytes():
            drift.append(rel)
    assert not missing, f"_playbook files with no repo counterpart: {missing}"
    assert not drift, f"_playbook files drifted from the repo (re-sync): {drift}"
