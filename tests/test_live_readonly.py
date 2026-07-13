"""Tier 1 — read-only live suite for the `wxcc-flow` CLI (`-m live`).

Codifies the 2026-07-11 fix-spec §8 command contracts + the Phase-C command
splits as repeatable pytest, plus the live doc-consistency invariants (registry
count == 52, every registry activity has a doc home, flowir §8 port table vs the
live outputPorts). Offline doc invariants (_index ↔ files, playbook byte-parity)
live in tests/test_doc_consistency.py so they run in the default suite.

Run:  pytest -m live                      # full Tier 1
      pytest -m "live and not portaudit"  # skip the per-activity port audit
Auto-skips when no token resolves. Every contract verified live on produs1
(org ccbcamp0199) 2026-07-12.
"""
from __future__ import annotations

import json
import re

import pytest

from tests.conftest import (
    REPO,
    READ_ONLY,
    API_TOLERATE_404,
    API_WARN,
    API_SKIP_INTERACTION,
    run_cli,
)

pytestmark = pytest.mark.live

FLOWIR = REPO / "docs" / "reference" / "flow-designer-flowir.md"


# ========================================================= Task 1a: porcelain
def test_list_paginates_past_ten(flows):
    # org has 51 flows; the old GET /flows size=10 default silently truncated.
    assert len(flows) > 10, f"expected >10 flows (pagination proof); got {len(flows)}"


def test_search_case_insensitive_substring(flows, a_flow_id):
    name = next(f["name"] for f in flows if f["id"] == a_flow_id)
    token = next((w for w in re.split(r"[-_ ]", name) if len(w) >= 4), None)
    if not token:
        pytest.skip(f"no usable substring in flow name {name!r}")
    lower = run_cli("search", token.lower(), "-o", "json")
    upper = run_cli("search", token.upper(), "-o", "json")
    assert lower.code == 0 and upper.code == 0, (lower.err, upper.err)
    lo, up = json.loads(lower.out), json.loads(upper.out)
    assert lo and up, f"case-insensitive substring {token!r} returned nothing"
    assert {f["id"] for f in lo} == {f["id"] for f in up}, "case sensitivity leaked"


def test_describe_flat_shape():
    r = run_cli("describe", "cryptographic-hash", "-o", "json")
    assert r.code == 0, r.err
    d = json.loads(r.out)
    assert {"inputs", "outputPorts", "activityType"} <= set(d), sorted(d)
    assert isinstance(d["inputs"], list) and len(d["inputs"]) > 0, "inputs should render"
    assert isinstance(d["outputPorts"], list), "outputPorts should render as a list"
    assert not ({"inputGroups", "component", "shapeProperties"} & set(d)), (
        "prod uses the FLAT definition shape (no inputGroups/component/shapeProperties)"
    )


def test_schema_renders_template():
    r = run_cli("schema", "cryptographic-hash")
    assert r.code == 0, r.err
    assert any(t in r.out for t in ("cryptographic-hash", "HashOutput", "error")), r.out[:200]


def test_choices_static_input():
    r = run_cli("choices", "queue-contact", "channelType", "-o", "json")
    assert r.code == 0, r.err
    d = json.loads(r.out)
    assert d.get("choices") and d.get("count", 0) > 0, d


def test_choices_cascading_requires_parent():
    r = run_cli("choices", "queue-contact", "destination", "-o", "json")
    assert r.code != 0, "a cascading input queried without its parent should error"
    assert "parent" in r.combined.lower(), r.combined[:200]


def test_choices_cascading_with_parent():
    r = run_cli(
        "choices", "queue-contact", "destination",
        "--parent-input", "channelType", "--parent-value", "TELEPHONY", "-o", "json",
    )
    assert r.code == 0, r.err
    d = json.loads(r.out)
    assert d.get("source") == "dynamic" and "choices" in d, d


def test_test_expr_sends_expr_field():
    r = run_cli("test-expr", "--expr", "{{ 1 + 1 }}", "-o", "json")
    assert r.code == 0, r.err
    d = json.loads(r.out)
    assert d.get("isValid") is True and d.get("generatedValue") == "2", d


def test_export_round_trips(a_flow_id):
    r = run_cli("export", a_flow_id, "-o", "json")
    assert r.code == 0, r.err
    d = json.loads(r.out)
    assert "nodes" in d and "edges" in d, sorted(d)


def test_global_vars_returns_metadata():
    r = run_cli("global-vars", "-o", "json")
    assert r.code == 0, r.err
    d = json.loads(r.out)
    assert isinstance(d, list) and d and {"name", "type"} <= set(d[0]), d[:1]


def test_version_draft_renders(a_flow_id):
    r = run_cli("version-draft", a_flow_id, "-o", "json")
    assert r.code == 0, r.err
    d = json.loads(r.out)
    assert d.get("flowId") == a_flow_id and "id" in d, sorted(d)


def test_version_latest_and_by_id(pub_version):
    fid, vid = pub_version
    latest = run_cli("version-latest", fid, "-o", "json")
    assert latest.code == 0, latest.err
    assert "id" in json.loads(latest.out)
    byid = run_cli("version-by-id", fid, vid, "-o", "json")
    assert byid.code == 0, byid.err
    assert json.loads(byid.out).get("id") == vid


def test_validate_id_wires_up(a_flow_id):
    # validate-id emits the FLOW-only warn banner; on some drafts the server 500s
    # ("Oops... Something broke...") — tolerated. A CLI crash (Traceback) is not.
    r = run_cli("validate-id", a_flow_id, "--version-id", "draft")
    assert "Warning:" in r.combined, "expected the FLOW-only validate warn banner"
    assert "Traceback" not in r.combined, r.combined[:300]


def test_all_versions_latest_warns_before_call():
    r = run_cli("all-versions-latest", "-o", "json")
    # warn banner precedes the call; may 500 org-wide (documented paged fallback).
    assert "Warning:" in r.err, r.err[:200]


def test_events_points_to_eventflows():
    r = run_cli("events")
    assert "eventFlows" in r.combined and "flowir" in r.combined.lower(), r.combined[:200]


# ===================================================== Task 1a2: api namespace
def _resolve_api_argv(entry, *, flow_id, version_id, template_id):
    """argv (list) for a read-only api command, or (None, skip_reason).
    All recipes verified live 2026-07-12."""
    g, c = entry["group"], entry["command"]
    base = ["api", g, c]
    if (g, c) in API_SKIP_INTERACTION:
        return None, "needs real interaction data (no live call routed to a flow)"
    if (g, c) == ("flows", "check"):
        return base + ["--search", "a", "-o", "json"], None
    if (g, c) == ("flows", "search"):
        return base + ["a", "-o", "json"], None
    if (g, c) == ("flows-v2", "choices"):
        return base + ["queue-contact", "channelType", "-o", "json"], None
    if (g, c) == ("flows-v2", "describe"):
        return base + ["cryptographic-hash", "-o", "json"], None
    if (g, c) == ("connectors", "get"):
        return None, "connector-controller 404s on system project; no valid id"
    argv = list(base)
    for p in entry.get("required_params") or []:
        if p == "<flowId>":
            argv.append(flow_id)
        elif p == "<versionId>":
            if version_id is None:
                return None, "no published version available"
            argv.append(version_id)
        elif p == "<id>":
            if template_id is None:
                return None, "no template available"
            argv.append(template_id)
        else:
            return None, f"resolver has no recipe for param {p!r}"
    return argv + ["-o", "json"], None


@pytest.mark.parametrize("entry", READ_ONLY, ids=lambda e: f"{e['group']}.{e['command']}")
def test_api_readonly_returns_or_parses(entry, a_flow_id, request):
    rp = entry.get("required_params") or []
    key = (entry["group"], entry["command"])
    # Commands that read a PUBLISHED version must use a known-published flow, not
    # flows[0] (whose publish state is non-deterministic). `versions latest`
    # returns the latest published version and 404s on a never-published flow;
    # `versions list` returns [] there — route both through pub_version.
    if "<versionId>" in rp:  # a versionId must pair with ITS OWN parent flow
        flow_id, version_id = request.getfixturevalue("pub_version")
    elif key in {("versions", "latest"), ("versions", "list")}:
        flow_id, version_id = request.getfixturevalue("pub_version")[0], None
    else:
        flow_id, version_id = a_flow_id, None
    template_id = (
        request.getfixturevalue("a_template_id")
        if (entry["group"], entry["command"]) == ("templates", "get") else None
    )
    argv, skip = _resolve_api_argv(
        entry, flow_id=flow_id, version_id=version_id, template_id=template_id
    )
    if skip:
        pytest.skip(skip)
    r = run_cli(*argv)
    key = (entry["group"], entry["command"])
    if key in API_TOLERATE_404:
        assert r.code != 0 and "404" in r.combined, (
            f"expected the documented system-project 404: {r.combined[:200]}"
        )
        return
    if key in API_WARN:
        assert "Warning:" in r.err, f"expected the warn banner: {r.err[:200]}"
        return  # may 500 org-wide (tolerated)
    assert r.code == 0, f"{argv} -> exit {r.code}: {r.combined[:300]}"
    if r.out.strip()[:1] in "{[":
        json.loads(r.out)  # emitted JSON parses


# ================================================ Task 1b: doc-consistency (live)
def _flowir_registry_ports():
    """Map activityName -> set of backtick-quoted port tokens from flowir §8."""
    text = FLOWIR.read_text()
    seg = text.split("## 8. Complete Activity Registry", 1)[1].split("## 9.", 1)[0]
    out = {}
    for line in seg.splitlines():
        cells = [c.strip() for c in line.split("|")]
        # rows: | `name` | Display | `group` | ports... |  -> cells[1]=name, cells[4]=ports
        if len(cells) >= 6 and cells[1].startswith("`") and cells[1].endswith("`"):
            out[cells[1].strip("`")] = set(re.findall(r"`([^`]+)`", cells[4]))
    return out


def test_registry_count_is_52(activities):
    assert len(activities) == 52, (
        f"live registry has {len(activities)} activities; docs assume 52. If Cisco "
        "changed it, update BOTH this test and flowir.md §8 + the CLAUDE.md count, "
        "and flag it loudly."
    )


def test_every_registry_activity_has_a_doc_home(activity_names):
    documented = set(_flowir_registry_ports())
    missing = [a for a in activity_names if a not in documented]
    assert not missing, f"registry activities absent from the flowir §8 table: {missing}"


# Ports the API leaves IMPLICIT (out/default), or that are dynamic per config —
# flowir §8 documents them, so they are exempt from the live-vs-doc check.
_DYNAMIC_PORT_ACTIVITIES = {"case-statement", "percent-allocation", "ivr-menu"}


@pytest.mark.portaudit
def test_flowir_port_table_documents_live_ports(activities):
    """Every EXPLICIT live output port appears in flowir §8. Implicit success
    ports (out/default) are documented but absent from the API's outputPorts
    array, so the reverse is intentionally NOT asserted."""
    doc = _flowir_registry_ports()
    problems = []
    for e in activities:
        name = e["activityName"]
        if name in _DYNAMIC_PORT_ACTIVITIES or name not in doc:
            continue
        live = {p["condition"] for p in (e.get("outputPorts") or [])}
        undocumented = live - doc[name]
        if undocumented:
            problems.append(
                f"{name}: live ports {sorted(undocumented)} not in flowir §8 {sorted(doc[name])}"
            )
    assert not problems, "\n".join(problems)
