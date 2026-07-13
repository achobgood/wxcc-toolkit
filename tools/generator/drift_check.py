#!/usr/bin/env python3
"""Drift gate — mechanical coherence checks between the Flow Store spec
snapshot, the overrides YAML, the emitted CLI, and the docs (design § 12).

Report-only by default (always exits 0); --enforce exits 1 on any failure.
Checks:
  0. Generator artifacts are git-tracked (fresh-clone semantics).
  1. Spec <-> manifest parity: the overrides partition every spec op into
     exactly one of {generated, blocked, skip_endpoints, skip_tags}; the
     manifest's operationIds equal the generated+blocked set; extra rows
     clone existing ops; warn/blocked statuses and top_level annotations
     match the YAML.
  2. Emitted-source URLs: every non-blocked manifest op's (METHOD, path) is
     actually called in src/wxcc_flow/generated/*.py, and every URL called
     there maps back to a spec operation (no invented paths).
  3. CLI root surface: registered root commands == manifest top_level names
     + keep_endpoints hand survivors (both directions).
  4. Documented counts: CLAUDE.md / README.md "N commands over the live
     M-operation contract" claims match the measured surface.
  5. Dead references: every `wxcc-flow <cmd>` / `wxcc-flow api <group> <op>`
     token in code spans of CLAUDE.md, README.md, .claude/**, docs/reference/**
     and docs/playbooks/** resolves against the built CLI.

Run: uv run python tools/generator/drift_check.py [--enforce] [--json]
Ported from wxcli tools/drift_check.py; YAML via PyYAML (no regex parsing).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / "specs" / "flow-store-api-docs.json"
OVERRIDES_PATH = REPO / "tools" / "generator" / "flow-store-overrides.yaml"
GENERATED_DIR = REPO / "src" / "wxcc_flow" / "generated"
MANIFEST_PATH = GENERATED_DIR / "_manifest.json"
ALLOWLIST_PATH = REPO / "tools" / "generator" / "drift_check_allowlist.txt"

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
TRACKED_ARTIFACTS = (
    "specs/flow-store-api-docs.json",
    "tools/generator/generate.py",
    "tools/generator/parser.py",
    "tools/generator/renderer.py",
    "tools/generator/pull_spec.py",
    "tools/generator/drift_check.py",
    "tools/generator/flow-store-overrides.yaml",
    "src/wxcc_flow/generated/_manifest.json",
)
SCAN_PATTERNS = ("CLAUDE.md", "README.md", ".claude/skills/**",
                 ".claude/agents/**", ".claude/rules/**",
                 "docs/reference/**", "docs/playbooks/**")


def tracked_files(*patterns: str) -> set:
    out = subprocess.run(["git", "ls-files", "--", *patterns],
                         capture_output=True, text=True, cwd=REPO, check=True)
    return {line for line in out.stdout.splitlines() if line}


def norm_path(path: str) -> str:
    """Normalize an API path for matching: every {param} -> {}."""
    return re.sub(r"\{[^}]*\}", "{}", path)


def load_spec_ops() -> dict:
    """{operationId: {"method", "path", "tags"}} for every spec operation."""
    spec = json.loads(SPEC_PATH.read_text())
    ops = {}
    for path, item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            op_id = op.get("operationId") or f"{method.upper()} {path}"
            ops[op_id] = {"method": method.upper(), "path": path,
                          "tags": op.get("tags") or []}
    return ops


def load_overrides() -> dict:
    return yaml.safe_load(OVERRIDES_PATH.read_text()) or {}


def classify_spec_ops(spec_ops: dict, ov: dict):
    """Partition spec ops by overrides; also return classification errors."""
    errors = []
    skip_tags = set(ov.get("skip_tags") or [])
    skip_eps = set(ov.get("skip_endpoints") or {})
    blocked = set(ov.get("blocked_endpoints") or {})
    for name, listed in (("skip_endpoints", skip_eps), ("blocked_endpoints", blocked)):
        for op_id in sorted(listed - set(spec_ops)):
            errors.append(f"{name} lists unknown operationId '{op_id}'")
    classes = {"generated": set(), "blocked": set(),
               "skip_endpoint": set(), "skip_tag": set()}
    for op_id, op in spec_ops.items():
        tag_skipped = any(t in skip_tags for t in op["tags"])
        if sum([tag_skipped, op_id in skip_eps, op_id in blocked]) > 1:
            errors.append(f"'{op_id}' classified more than once (tag-skip/skip/block overlap)")
        if op_id in blocked:
            classes["blocked"].add(op_id)
        elif op_id in skip_eps:
            classes["skip_endpoint"].add(op_id)
        elif tag_skipped:
            classes["skip_tag"].add(op_id)
        else:
            classes["generated"].add(op_id)
    return classes, errors


# ------------------------------------------------------------------ check 0

def check_artifacts_tracked() -> list:
    problems = []
    tracked = tracked_files("specs/*", "tools/generator/*", "src/wxcc_flow/generated/*")
    for rel in TRACKED_ARTIFACTS:
        if rel not in tracked:
            problems.append(f"not git-tracked: {rel}")
    for py in sorted(GENERATED_DIR.glob("*.py")):
        rel = py.relative_to(REPO).as_posix()
        if rel not in tracked:
            problems.append(f"emitted module not git-tracked: {rel}")
    return problems


# ------------------------------------------------------------------ check 1

def check_manifest_parity(spec_ops: dict, classes: dict, ov: dict, manifest: list) -> list:
    problems = []
    base_rows = [r for r in manifest if not r.get("extra")]
    extra_rows = [r for r in manifest if r.get("extra")]
    base_ids = [r["operationId"] for r in base_rows]
    if len(base_ids) != len(set(base_ids)):
        dupes = sorted({i for i in base_ids if base_ids.count(i) > 1})
        problems.append(f"duplicate non-extra manifest operationIds: {dupes}")
    manifest_ids = set(base_ids)
    for r in extra_rows:
        if r["operationId"] not in manifest_ids:
            problems.append(
                f"extra row '{r['command']}' clones unknown op '{r['operationId']}'")
    expected = classes["generated"] | classes["blocked"]
    for op_id in sorted(expected - manifest_ids):
        problems.append(f"spec op missing from manifest: {op_id}")
    for op_id in sorted(manifest_ids - set(spec_ops)):
        problems.append(f"manifest op not in spec: {op_id}")
    skipped = classes["skip_endpoint"] | classes["skip_tag"]
    for op_id in sorted(manifest_ids & skipped):
        problems.append(f"manifest contains a skipped op: {op_id}")
    by_id = {r["operationId"]: r for r in base_rows}
    for op_id in sorted(classes["blocked"] & manifest_ids):
        if by_id[op_id].get("status") != "blocked":
            problems.append(f"blocked_endpoints op '{op_id}' lacks status=blocked in manifest")
    for op_id in sorted(set(ov.get("warn_endpoints") or {}) & manifest_ids):
        if by_id[op_id].get("status") != "warn":
            problems.append(f"warn_endpoints op '{op_id}' lacks status=warn in manifest")
    # top_level annotations: YAML promotions + extra-clone promotions, exactly.
    # Base promotions key by operationId alone (unique among non-extra rows,
    # checked above) so the check holds even for ops without a command_names
    # entry; extra clones key by (operationId, clone name).
    manifest_top = {("base", r["operationId"]): r["top_level"]
                    for r in manifest if r.get("top_level") and not r.get("extra")}
    manifest_top.update({("extra", (r["operationId"], r["command"])): r["top_level"]
                         for r in manifest if r.get("top_level") and r.get("extra")})
    expected_top = {("base", op_id): top
                    for op_id, top in (ov.get("top_level_commands") or {}).items()}
    for op_id, clones in (ov.get("extra_commands") or {}).items():
        for clone in clones or []:
            if clone.get("top_level"):
                expected_top[("extra", (op_id, clone["name"]))] = clone["top_level"]
    for key in sorted(set(expected_top) - set(manifest_top)):
        problems.append(f"promotion missing from manifest: {key} -> {expected_top[key]}")
    for key in sorted(set(manifest_top) - set(expected_top)):
        problems.append(f"manifest top_level not in overrides: {key} -> {manifest_top[key]}")
    for key in sorted(set(expected_top) & set(manifest_top)):
        if expected_top[key] != manifest_top[key]:
            problems.append(
                f"promotion name mismatch for {key}: "
                f"overrides say '{expected_top[key]}', manifest says '{manifest_top[key]}'")
    return problems


# ------------------------------------------------------------------ check 2

VERB_METHOD = {"get": "GET", "get_safe": "GET", "get_text": "GET",
               "post": "POST", "post_multipart": "POST", "put": "PUT",
               "patch": "PATCH", "delete": "DELETE", "delete_with_body": "DELETE"}
_URL_CALL = re.compile(
    r'_path = f?"([^"]+)"'
    r'|c\.(get_safe|get_text|post_multipart|delete_with_body|post|put|patch|delete|get)'
    r'\((?:f?"([^"]+)"|_path)')


def emitted_urls() -> set:
    """(METHOD, normalized-path) pairs actually called in emitted source."""
    pairs = set()
    for py in sorted(GENERATED_DIR.glob("*.py")):
        current = None
        for m in _URL_CALL.finditer(py.read_text()):
            if m.group(1):
                current = m.group(1)
            elif m.group(2):
                url = m.group(3) or current
                if url:
                    pairs.add((VERB_METHOD[m.group(2)], norm_path(url)))
    return pairs


def check_source_urls(spec_ops: dict, manifest: list) -> list:
    problems = []
    pairs = emitted_urls()
    spec_pairs = {(op["method"], norm_path(op["path"])) for op in spec_ops.values()}
    for r in manifest:
        if r.get("status") == "blocked":
            continue
        want = (r["method"], norm_path(r["path"]))
        if want not in pairs:
            problems.append(
                f"manifest op '{r['operationId']}' URL not called in emitted "
                f"source: {r['method']} {r['path']}")
    for method, path in sorted(pairs - spec_pairs):
        problems.append(f"emitted source calls a URL not in the spec: {method} {path}")
    return problems


# ------------------------------------------------------------------ check 3

def cli_root_surface():
    """(root command names, {api group: {command names}}) from the built CLI."""
    from typer.main import get_command_name
    from wxcc_flow.main import app

    def cmd_names(typer_app):
        return {get_command_name(ci.name or ci.callback.__name__)
                for ci in typer_app.registered_commands}

    root = cmd_names(app)
    api_groups = {}
    for g in app.registered_groups:
        if g.name == "api":
            for sub in g.typer_instance.registered_groups:
                api_groups[sub.name] = cmd_names(sub.typer_instance)
    return root, api_groups


def check_cli_root(ov: dict, manifest: list, root: set) -> list:
    problems = []
    promoted = {r["top_level"] for r in manifest if r.get("top_level")}
    keep = set(ov.get("keep_endpoints") or [])
    for name in sorted(root - promoted - keep):
        problems.append(
            f"root command '{name}' is neither generated (manifest top_level) "
            f"nor excused in keep_endpoints")
    for name in sorted(keep - root):
        problems.append(f"keep_endpoints excuses '{name}' but no such root command exists")
    for name in sorted(promoted - root):
        problems.append(f"manifest top_level '{name}' is not registered at the root")
    return problems


# ------------------------------------------------------------------ check 4

_CLAIM = re.compile(r"(\d+)\s+commands? over the live (\d+)-operation contract")


def check_doc_counts(spec_ops: dict, manifest: list, ov: dict) -> list:
    problems = []
    measured_root = (len({r["top_level"] for r in manifest if r.get("top_level")})
                     + len(ov.get("keep_endpoints") or []))
    for rel in ("CLAUDE.md", "README.md"):
        p = REPO / rel
        if not p.exists():
            continue
        for m in _CLAIM.finditer(p.read_text()):
            n_cmd, n_ops = int(m.group(1)), int(m.group(2))
            if n_cmd != measured_root:
                problems.append(
                    f"{rel}: claims '{n_cmd} commands', measured {measured_root} root commands")
            if n_ops != len(spec_ops):
                problems.append(
                    f"{rel}: claims '{n_ops}-operation contract', spec has {len(spec_ops)} ops")
    return problems


# ------------------------------------------------------------------ check 5

_TOKEN = re.compile(
    r"wxcc-flow\s+([a-z0-9][a-z0-9_-]*)"
    r"(?:\s+([a-z0-9][a-z0-9_-]*))?(?:\s+([a-z0-9][a-z0-9_-]*))?")


def code_spans(text: str):
    """Yield (line_number, span_text) for fenced blocks and inline code."""
    fence_open = None
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence_open = None if fence_open else lineno
            continue
        if fence_open:
            if not line.lstrip().startswith("#"):  # shell comments are prose
                yield lineno, line
        else:
            for span in re.findall(r"`([^`]+)`", line):
                yield lineno, span


def load_allowlist() -> set:
    if not ALLOWLIST_PATH.exists():
        return set()
    return {line.strip() for line in ALLOWLIST_PATH.read_text().splitlines()
            if line.strip() and not line.startswith("#")}


def check_references(root: set, api_groups: dict) -> list:
    dead, allow = [], load_allowlist()
    for rel in sorted(f for f in tracked_files(*SCAN_PATTERNS) if f.endswith(".md")):
        text = (REPO / rel).read_text()
        for lineno, span in code_spans(text):
            for m in _TOKEN.finditer(span):
                first, second, third = m.group(1), m.group(2), m.group(3)
                entry = " ".join(t for t in (first, second, third) if t)
                if entry in allow or first in allow:
                    continue
                if first != "api":
                    if first not in root:
                        dead.append({"file": rel, "line": lineno,
                                     "ref": f"wxcc-flow {first}", "kind": "command"})
                    continue
                if second is None:
                    continue  # bare `wxcc-flow api` mention
                if second not in api_groups:
                    dead.append({"file": rel, "line": lineno,
                                 "ref": f"wxcc-flow api {second}", "kind": "api group"})
                elif third and third not in api_groups[second]:
                    dead.append({"file": rel, "line": lineno,
                                 "ref": f"wxcc-flow api {second} {third}",
                                 "kind": "api command"})
    return dead


# --------------------------------------------------------------------- main

def run_checks() -> dict:
    spec_ops = load_spec_ops()
    ov = load_overrides()
    manifest = json.loads(MANIFEST_PATH.read_text())
    classes, class_errors = classify_spec_ops(spec_ops, ov)
    root, api_groups = cli_root_surface()
    return {
        "counts": {
            "spec_ops": len(spec_ops),
            "generated": len(classes["generated"]),
            "blocked": len(classes["blocked"]),
            "skip_endpoints": len(classes["skip_endpoint"]),
            "skip_tags": len(classes["skip_tag"]),
            "manifest_rows": len(manifest),
            "manifest_unique_ops": len({r["operationId"] for r in manifest}),
            "manifest_extras": sum(1 for r in manifest if r.get("extra")),
            "top_level": sum(1 for r in manifest if r.get("top_level")),
            "keep_endpoints": len(ov.get("keep_endpoints") or []),
            "root_commands": len(root),
        },
        "0_artifacts_tracked": check_artifacts_tracked(),
        "1_spec_manifest_parity": class_errors
            + check_manifest_parity(spec_ops, classes, ov, manifest),
        "2_source_urls": check_source_urls(spec_ops, manifest),
        "3_cli_root_surface": check_cli_root(ov, manifest, root),
        "4_documented_counts": check_doc_counts(spec_ops, manifest, ov),
        "5_dead_references": check_references(root, api_groups),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--enforce", action="store_true",
                    help="exit 1 on any failing check (default: report only)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    results = run_checks()
    check_keys = [k for k in results if k != "counts"]
    failed = any(results[k] for k in check_keys)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        c = results["counts"]
        print(f"drift-check: {c['spec_ops']} spec ops = {c['generated']} generated "
              f"+ {c['blocked']} blocked + {c['skip_endpoints']} skip_endpoints "
              f"+ {c['skip_tags']} skip_tags")
        print(f"             manifest {c['manifest_rows']} rows = "
              f"{c['manifest_unique_ops']} unique ops + {c['manifest_extras']} extras; "
              f"{c['top_level']} top_level; root = {c['root_commands']} commands "
              f"({c['keep_endpoints']} hand survivors excused)\n")
        for key in check_keys:
            problems = results[key]
            print(f"[{key}] {len(problems)} problem(s)")
            for p in problems[:20]:
                if isinstance(p, dict):
                    print(f"      {p['file']}:{p['line']}  {p['ref']}  (dead {p['kind']})")
                else:
                    print(f"      {p}")
            if len(problems) > 20:
                print(f"      ... and {len(problems) - 20} more (--json for all)")
        print(f"\nresult: {'FAIL' if failed else 'PASS'}"
              f"{' (advisory — not enforcing)' if failed and not args.enforce else ''}")

    return 1 if (failed and args.enforce) else 0


if __name__ == "__main__":
    sys.exit(main())
