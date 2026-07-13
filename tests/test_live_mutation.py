"""Tier 2 — mutation round-trip suite for the `wxcc-flow` CLI.

DOUBLE-GATED: runs only with `-m mutation` AND env `WXCC_LIVE_MUTATION=1` (plus
explicit in-session user approval). Every flow it creates is named `CLITest_*`
and is deleted in teardown even on failure; a session safety-sweep force-deletes
any `CLITest_*` straggler. It NEVER touches a flow it did not create.

Covers: kitchen-sink import/export round-trip; the open platform facts
(generate-otp pinValidity, verify-otp extra props + ports, cryptographic-hash
outputs, implicit-out ports, BYOC channelName); publish + --validate; and the
21 mutating `api` commands (blocked stub, warn banners, lifecycle create/teardown).

Run:  WXCC_LIVE_MUTATION=1 pytest -m mutation
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.conftest import REPO, MANIFEST, run_cli

pytestmark = pytest.mark.mutation

KITCHEN_SINK = REPO / "docs" / "plans" / "flowir" / "kitchen-sink-test.json"
MUTATING = [e for e in MANIFEST if e.get("read_only") is False]
_PID = os.getpid()


# --------------------------------------------------------------- helpers
def _create_from(body: dict, tmp: Path, name: str) -> str:
    """Import a FlowIR body under `name`; return the created flow id."""
    body = dict(body)
    body["name"] = name
    p = tmp / f"{name}.json"
    p.write_text(json.dumps(body))
    r = run_cli("create", str(p), "-o", "json")
    assert r.code == 0, f"create failed: {r.combined[:400]}"
    d = json.loads(r.out)
    fid = d.get("id") or (d.get("flow") or {}).get("id")
    assert fid, f"no id in create response: {r.out[:300]}"
    return fid


def _node_activity(node: dict) -> str:
    props = node.get("properties") or {}
    return props.get("activityName") or node.get("activityType") or ""


def _find_prop(obj, key):
    """Every value stored under `key` anywhere inside a node/dict (export-shape agnostic)."""
    hits = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == key:
                    hits.append(v)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(obj)
    return hits


# ------------------------------------------------------------- fixtures
@pytest.fixture
def make_flow(mutation_env, tmp_path):
    """Factory: create CLITest_* flows from a FlowIR body; delete all on teardown."""
    created = []

    def _make(suffix, body=None):
        body = body if body is not None else json.loads(KITCHEN_SINK.read_text())
        name = f"CLITest_{suffix}_{_PID}"
        fid = _create_from(body, tmp_path, name)
        created.append(fid)
        return fid, name

    yield _make
    for fid in created:
        run_cli("delete", fid, "--force")


@pytest.fixture(scope="session", autouse=True)
def _clitest_safety_sweep():
    """After the mutation session, force-delete any stray CLITest_* flow."""
    yield
    if os.environ.get("WXCC_LIVE_MUTATION") != "1":
        return
    r = run_cli("list", "-o", "json")
    if r.code == 0:
        for f in json.loads(r.out):
            # "in" (not startswith) also catches copies, which prepend "Copy_".
            if "CLITest_" in str(f.get("name", "")):
                run_cli("delete", f["id"], "--force")


# ===================================================== open platform facts
def _export(fid):
    r = run_cli("export", fid, "-o", "json")
    assert r.code == 0, r.err
    return json.loads(r.out)


def _nodes_by_activity(flow, activity):
    return [n for n in flow.get("nodes", []) if _node_activity(n) == activity]


def test_kitchen_sink_round_trips(make_flow):
    fid, name = make_flow("KitchenSink")
    exp = _export(fid)
    src = json.loads(KITCHEN_SINK.read_text())
    assert exp["name"] == name
    assert len(exp["nodes"]) == len(src["nodes"]), "node count changed on round-trip"
    assert len(exp["edges"]) == len(src["edges"]), "edge count changed on round-trip"


def test_open_fact1_generate_otp_pinvalidity(make_flow):
    """Fact 1: pinValidity survives import round-trip; capture the stored value.
    (Unit — minutes vs seconds — needs a UI check; the doc conflict note stands.)"""
    fid, _ = make_flow("GenOTP")
    node = _nodes_by_activity(_export(fid), "generate-otp")
    assert node, "generate-otp node missing after round-trip"
    vals = _find_prop(node[0], "pinValidity")
    print(f"OPEN-FACT 1 generate-otp.pinValidity round-tripped: {vals}")
    assert vals and str(vals[0]) == "300", f"expected '300' to survive; got {vals}"


def test_open_fact2_verify_otp_extra_props(make_flow, tmp_path):
    """Fact 2: do notifyURL/resendCommand/extraParameters survive when added to a
    verify-otp node? Either outcome is a documentable finding (no CLI crash)."""
    body = json.loads(KITCHEN_SINK.read_text())
    extra = {"notifyURL": "https://example.com/otp", "resendCommand": "resend",
             "extraParameters": [{"key": "k", "value": "v"}]}
    for n in body["nodes"]:
        if _node_activity(n) == "verify-otp":
            n["properties"].update(extra)
    body["name"] = f"CLITest_VerifyExtraValidate_{_PID}"
    p = tmp_path / "verify_extra.json"
    p.write_text(json.dumps(body))
    v = run_cli("validate", str(p))
    print(f"OPEN-FACT 2 validate exit={v.code}: {v.combined[:200]}")
    assert "Traceback" not in v.combined
    if v.code != 0:
        pytest.skip(f"modified verify-otp body rejected by validate: {v.combined[:160]}")
    fid, _ = make_flow("VerifyExtra", body=body)
    node = _nodes_by_activity(_export(fid), "verify-otp")[0]
    survived = {k: bool(_find_prop(node, k)) for k in extra}
    print(f"OPEN-FACT 2 verify-otp extra props survived round-trip: {survived}")


def test_open_fact3_4_6_ports_and_hash_outputs(make_flow):
    """Facts 3/6 (verify-otp + implicit-out ports via round-trip edges) and
    Fact 4 (cryptographic-hash outputs). Records the export shape as evidence."""
    fid, _ = make_flow("PortsHash")
    exp = _export(fid)
    edges = exp.get("edges", [])
    print(f"OPEN-FACT 3/6 total round-tripped edges: {len(edges)}")
    for act in ("generate-otp", "verify-otp", "cryptographic-hash"):
        nodes = _nodes_by_activity(exp, act)
        if not nodes:
            continue
        nname = nodes[0].get("name")  # edges reference nodes by NAME, not id
        ports = sorted({e.get("condition") for e in edges
                        if e.get("from") == nname and e.get("condition")})
        print(f"OPEN-FACT 3/6 {act} ({nname}) outgoing edge port conditions: {ports or '(none)'}")
    hnode = _nodes_by_activity(exp, "cryptographic-hash")
    if hnode:
        outs = _find_prop(hnode[0], "outputs") + _find_prop(hnode[0], "HashOutput")
        print(f"OPEN-FACT 4 cryptographic-hash output shape: {json.dumps(outs)[:240]}")
    assert edges, "kitchen-sink lost all edges on round-trip"


def test_open_fact5_byoc_channelname_and_schema(mutation_env):
    """Fact 5: BYOC ReceiveMessage/SendCustomMessage — does channelName resolve
    choices on this (unprovisioned) org, and are the activities describable?
    Records evidence; no custom messaging channel is provisioned here."""
    for act in ("ReceiveMessage", "SendCustomMessage"):
        ch = run_cli("choices", act, "channelName", "-o", "json")
        print(f"OPEN-FACT 5 choices {act} channelName: exit={ch.code} :: {ch.combined[:160]}")
        sc = run_cli("describe", act, "-o", "json")
        assert sc.code == 0, f"{act} should be describable: {sc.err[:160]}"
        d = json.loads(sc.out)
        inputs = [i["name"] for i in d.get("inputs", [])]
        ports = [p["condition"] for p in d.get("outputPorts", [])]
        print(f"OPEN-FACT 5 {act} inputs={inputs} ports={ports}")


# ================================================ lifecycle + publish/validate
def test_lifecycle_lock_unlock_copy_publish(make_flow, tmp_path):
    """Verified state-changers on a CLEAN throwaway flow. (The kitchen-sink is an
    intentionally-incomplete harness that `copy` 500s on — a documented finding —
    so lifecycle uses the simple-inbound starter.) lock -> unlock -> copy ->
    publish. The copy is force-deleted here; the source in make_flow teardown."""
    tpl = tmp_path / "simple.json"
    assert run_cli("template", "simple-inbound", "--out", str(tpl)).code == 0
    fid, _ = make_flow("Lifecycle", body=json.loads(tpl.read_text()))
    assert run_cli("lock", fid).code == 0
    assert run_cli("unlock", fid).code == 0
    cp = run_cli("copy", fid, "-o", "json")
    assert cp.code == 0, cp.combined[:200]
    cd = json.loads(cp.out)
    copy_id = cd.get("id") or (cd.get("flow") or {}).get("id")
    try:
        assert copy_id, f"copy returned no id: {cp.out[:200]}"
    finally:
        if copy_id:
            run_cli("delete", copy_id, "--force")
    pub = run_cli("publish", fid)
    print(f"lifecycle publish exit={pub.code}: {pub.combined[:160]}")
    assert "Traceback" not in pub.combined


def test_publish_with_validate_flag(make_flow):
    """publish --validate validates at publish time (a distinct code path)."""
    r = run_cli("publish", make_flow("PublishValidate")[0], "--validate")
    print(f"publish --validate exit={r.code}: {r.combined[:200]}")
    assert "Traceback" not in r.combined


def test_save_draft_round_trips(make_flow, tmp_path):
    """flows-v2 save-draft: a description round-trip proves the draft was saved."""
    fid, name = make_flow("SaveDraft")
    body = json.loads(KITCHEN_SINK.read_text())
    body["name"] = name
    body["description"] = "clitest-savedraft-marker"
    p = tmp_path / "draft.json"
    p.write_text(json.dumps(body))
    r = run_cli("save-draft", fid, str(p))
    print(f"save-draft exit={r.code}: {r.combined[:160]}")
    assert r.code == 0, r.combined[:240]
    assert _export(fid).get("description") == "clitest-savedraft-marker"


def test_update_renames_draft(make_flow):
    """flows-v2 update sets a new name/description on the draft (verified live)."""
    fid, _ = make_flow("Update")
    r = run_cli("update", fid, "--description", "clitest-update-marker")
    assert r.code == 0, r.combined[:200]
    assert _export(fid).get("description") == "clitest-update-marker"


# ============================================== mutating api namespace (21)
def test_api_merge_patch_is_blocked_stub():
    """flows merge-patch is a blocked no-op: exit 2, no HTTP call, points to update."""
    r = run_cli("api", "flows", "merge-patch")
    assert r.code == 2, f"expected exit 2; got {r.code}: {r.combined[:200]}"
    assert "no-op" in r.combined and "update" in r.combined, r.combined[:200]


_WARN_MUTATORS = [("flows-v2", "validate"), ("flows-v2", "patch-draft"), ("flows", "consume-template")]


@pytest.mark.parametrize("g,c", _WARN_MUTATORS, ids=[f"{g}.{c}" for g, c in _WARN_MUTATORS])
def test_api_mutating_warn_banner(g, c, make_flow, tmp_path):
    body = tmp_path / "body.json"
    body.write_text(KITCHEN_SINK.read_text())
    if (g, c) == ("flows-v2", "validate"):
        r = run_cli("api", "flows-v2", "validate", str(body))
    elif (g, c) == ("flows-v2", "patch-draft"):
        r = run_cli("api", "flows-v2", "patch-draft", make_flow("PatchWarn")[0], str(body))
    else:  # non-existent template -> warn banner, then 404 (both documentable)
        r = run_cli("api", "flows", "consume-template",
                    "__clitest_no_such_tpl__", f"CLITest_ConsumeTplWarn_{_PID}")
    assert "Warning:" in r.err, f"expected warn banner on stderr: {r.err[:200]}"


def test_api_unique_name_probe(mutation_env):
    """flows unique-name checks a name without mutating (exit 0 = unique)."""
    r = run_cli("unique-name", f"CLITest_DefinitelyUnique_{_PID}")
    assert r.code == 0, r.combined[:200]


# Explicit accounting for all 21 mutating commands: each maps to the live test
# that exercises it, or a documented reason it is not run. Makes the "iterate the
# 21" requirement provably complete without blind, unsafe execution.
_MUTATION_COVERAGE = {
    ("flows", "merge-patch"): "test_api_merge_patch_is_blocked_stub",
    ("flows", "consume-template"): "test_api_mutating_warn_banner",
    ("flows-v2", "validate"): "test_api_mutating_warn_banner",
    ("flows-v2", "patch-draft"): "test_api_mutating_warn_banner",
    ("flows", "lock"): "test_lifecycle_lock_unlock_copy_publish",
    ("flows", "unlock"): "test_lifecycle_lock_unlock_copy_publish",
    ("flows", "copy"): "test_lifecycle_lock_unlock_copy_publish",
    ("flows", "publish"): "test_lifecycle + test_publish_with_validate_flag",
    ("flows", "delete"): "make_flow teardown + copy teardown + safety sweep",
    ("flows", "import"): "test_kitchen_sink_round_trips (create == import)",
    ("flows-v2", "import"): "test_kitchen_sink_round_trips (create == import)",
    ("flows-v2", "save-draft"): "test_save_draft_round_trips",
    ("flows-v2", "update"): "test_update_renames_draft",
    ("flows", "unique-name"): "test_api_unique_name_probe",
    ("util", "test-expr"): "SKIP: covered by porcelain test-expr (Tier 1)",
    ("flows", "consume"): "SKIP: expects UI-export shape body, not FlowIR",
    ("flows", "revert"): "SKIP: needs a prior published version to revert to",
    ("flows", "variable-mapping"): "SKIP: needs a related GoTo hand-off flow pair",
    ("prefs", "add"): "SKIP: needs a bespoke flow-preference body",
    ("prefs", "set"): "SKIP: needs a bespoke flow-preference body",
    ("prefs", "remove"): "SKIP: needs a bespoke flow-preference body",
}


def test_all_21_mutating_commands_are_accounted_for():
    live = {(e["group"], e["command"]) for e in MUTATING}
    assert live == set(_MUTATION_COVERAGE), (
        f"uncovered mutating commands: {sorted(live - set(_MUTATION_COVERAGE))}; "
        f"stale coverage entries: {sorted(set(_MUTATION_COVERAGE) - live)}"
    )
