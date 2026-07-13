"""Shared helpers + fixtures for the live `wxcc-flow` test tiers.

Tier 1 (`-m live`, tests/test_live_readonly.py) and Tier 2 (`-m mutation` +
`WXCC_LIVE_MUTATION=1`, tests/test_live_mutation.py) both drive the REAL
installed `wxcc-flow` binary as a subprocess, so they exercise the true command
surface, exit codes, and `-o json` output against live prod. Both tiers
auto-skip when the CLI or a token is unavailable.

Every JSON shape hard-coded below was verified live on produs1 (org
ccbcamp0199) 2026-07-12 — see docs/plans/2026-07-11-live-tests-kickoff-prompt.md.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

import wxcc_flow.config as cfg

# Keep the whole suite hermetic: the CLI's PyPI update check fires from the
# top-level callback on every in-process CliRunner call and every subprocess
# run_cli call. Disable it session-wide so no test ever reaches out to PyPI.
os.environ.setdefault("WXCC_FLOW_NO_UPDATE_CHECK", "1")

REPO = Path(__file__).resolve().parent.parent
MANIFEST = json.loads(
    (REPO / "src" / "wxcc_flow" / "generated" / "_manifest.json").read_text()
)
WXCC_BIN = shutil.which("wxcc-flow")


@dataclass
class CliResult:
    code: int
    out: str
    err: str
    argv: list

    def json(self):
        return json.loads(self.out)

    @property
    def combined(self) -> str:
        return self.out + self.err


def run_cli(*args, timeout=180) -> CliResult:
    """Invoke the installed `wxcc-flow` binary (which imports the working tree)."""
    argv = [WXCC_BIN, *[str(a) for a in args]]
    p = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, cwd=str(REPO)
    )
    return CliResult(p.returncode, p.stdout, p.stderr, argv)


# ---------------------------------------------------------------- skip guards
@pytest.fixture(scope="session")
def live_env():
    """Skip the whole live tier when the CLI or a token is unavailable."""
    if WXCC_BIN is None:
        pytest.skip("wxcc-flow not on PATH")
    if not cfg.resolve_token():
        pytest.skip("no token (config / WXCC_FLOW_TOKEN / WEBEX_ACCESS_TOKEN)")
    return True


@pytest.fixture(scope="session")
def mutation_env(live_env):
    """Tier 2 double-gate: `-m mutation` selects it; this adds the env flag."""
    if os.environ.get("WXCC_LIVE_MUTATION") != "1":
        pytest.skip("mutation tier requires WXCC_LIVE_MUTATION=1 (+ explicit approval)")
    return True


# --------------------------------------------------------- session discovery
@pytest.fixture(scope="session")
def activities(live_env):
    """Live activity registry — ONE call, reused by registry/doc-home/port tests.
    Each entry: activityName, displayName, group, inputs, outputs, outputPorts."""
    r = run_cli("activities", "-o", "json")
    assert r.code == 0, r.err
    data = json.loads(r.out)
    assert isinstance(data, list) and data
    return data


@pytest.fixture(scope="session")
def activity_names(activities):
    return sorted(e["activityName"] for e in activities)


@pytest.fixture(scope="session")
def flows(live_env):
    """Full flow list (entries keyed by 'id', 'name', 'status', 'flowType')."""
    r = run_cli("list", "-o", "json")
    assert r.code == 0, r.err
    return json.loads(r.out)


@pytest.fixture(scope="session")
def a_flow_id(flows):
    if not flows:
        pytest.skip("org has no flows")
    return flows[0]["id"]


@pytest.fixture(scope="session")
def pub_version(live_env):
    """(flow_id, version_id) for some PUBLISHED version; skip if project has none."""
    r = run_cli("all-versions", "--page", "0", "--size", "10", "-o", "json")
    if r.code != 0:
        pytest.skip(f"all-versions failed: {r.err[:160]}")
    vs = json.loads(r.out)
    if not vs:
        pytest.skip("no published versions in project")
    return vs[0]["flowId"], vs[0]["id"]


@pytest.fixture(scope="session")
def a_template_id(live_env):
    r = run_cli("templates", "-o", "json")
    if r.code != 0:
        pytest.skip(f"templates failed: {r.err[:160]}")
    ts = json.loads(r.out)
    if not ts:
        pytest.skip("no templates in project")
    return ts[0]["id"]


# ------------------------------------------------ read-only manifest routing
READ_ONLY = [e for e in MANIFEST if e.get("read_only") is True]
MUTATING = [e for e in MANIFEST if e.get("read_only") is False]

# api commands that legitimately fail on the system-provisioned project, warn,
# or need real interaction data — all verified live 2026-07-12. (group, command).
API_TOLERATE_404 = {("projects", "get"), ("connectors", "list"), ("connectors", "get")}
# read-only commands that print a "Warning:" banner to stderr and may exit non-zero
# (validate-id 500s on some drafts; all-latest 500s org-wide) — assert the banner,
# tolerate the exit code.
API_WARN = {("versions", "all-latest"), ("flows-v2", "validate-id")}
API_SKIP_INTERACTION = {
    ("tracing", "analytics"), ("tracing", "interaction"), ("tracing", "interactions"),
    ("tracing", "traces"), ("tracing", "traces-decrypt"),
}
