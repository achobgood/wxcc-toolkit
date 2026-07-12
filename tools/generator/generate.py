"""Generate the wxcc-flow `api` command namespace from the Flow Store spec.

Single-spec fork of /webexCalling generate_commands.py: no base-URL sniffing,
no dev-only block, no multi-spec override routing. One spec → one base URL
(resolved inside FlowClient). Emits src/wxcc_flow/generated/ with one module per
group, a register(app) entry point, a wholesale-rewritten _registry.py, and a
_manifest.json driving the prod verification sweep + parity gate.

Usage:
    python3 -m tools.generator.generate --list-groups
    python3 -m tools.generator.generate --all --dry-run
    python3 -m tools.generator.generate --all
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

import yaml

from .parser import load_spec, get_tags, parse_tag
from . import renderer as R

REPO = Path(__file__).resolve().parent.parent.parent
DEFAULT_SPEC = REPO / "specs" / "flow-store-api-docs.json"
DEFAULT_OVERRIDES = Path(__file__).resolve().parent / "flow-store-overrides.yaml"
DEFAULT_OUTPUT = REPO / "src" / "wxcc_flow" / "generated"

# opId-keyed override sections validated by the lint against the spec.
_OPID_SECTIONS = (
    "skip_endpoints", "blocked_endpoints", "warn_endpoints", "request_overrides",
    "param_cli_names", "pagination", "response_list_keys", "table_columns",
    "command_names", "help_notes", "output_file_option", "body_from_file",
    "body_fields_override", "body_transform", "exit_code_from",
    "param_flag_inversions", "command_type_overrides", "top_level_commands",
)


def _spec_index(spec: dict) -> tuple[set, dict]:
    """Return (all_tags, opId → op dict)."""
    tags: set = set()
    ops: dict = {}
    for path_obj in spec.get("paths", {}).values():
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_obj.get(method)
            if not op or not isinstance(op, dict):
                continue
            for t in op.get("tags", []):
                tags.add(t)
            oid = op.get("operationId")
            if oid:
                ops[oid] = op
    return tags, ops


def lint_overrides(overrides: dict, spec: dict) -> None:
    """FAIL if any override references a tag or operationId absent from the spec
    (design § 6 lint — machine-kills the wxcli 'silently matches nothing' gotcha)."""
    all_tags, ops = _spec_index(spec)
    errors: list = []
    # group source tags must exist
    for group, src_tags in (overrides.get("groups") or {}).items():
        for t in src_tags:
            if t not in all_tags:
                errors.append(f"groups.{group}: source tag {t!r} not in spec")
    # skip_tags globs must match at least one tag
    for pat in overrides.get("skip_tags") or []:
        if not any(fnmatch.fnmatch(t, pat) for t in all_tags):
            errors.append(f"skip_tags: pattern {pat!r} matches no spec tag")
    # every opId-keyed override must reference a real operationId
    for section in _OPID_SECTIONS:
        for oid in (overrides.get(section) or {}):
            if oid not in ops:
                errors.append(f"{section}: operationId {oid!r} not in spec")
    if errors:
        raise SystemExit("Override lint FAILED:\n  - " + "\n  - ".join(errors))


def build_resolver(overrides: dict):
    """Return resolve_ovr(ep) -> op_ovr dict (the renderer's per-command overrides)."""
    skip = overrides.get("skip_endpoints") or {}
    blocked = overrides.get("blocked_endpoints") or {}
    warns = overrides.get("warn_endpoints") or {}
    req_ovr = overrides.get("request_overrides") or {}
    cli_names = overrides.get("param_cli_names") or {}
    pagination = overrides.get("pagination") or {}
    list_keys = overrides.get("response_list_keys") or {}
    columns = overrides.get("table_columns") or {}
    names = overrides.get("command_names") or {}
    notes = overrides.get("help_notes") or {}
    out_file = overrides.get("output_file_option") or {}
    body_file = overrides.get("body_from_file") or {}
    body_extra = overrides.get("body_fields_override") or {}
    body_xf = overrides.get("body_transform") or {}
    exit_codes = overrides.get("exit_code_from") or {}
    inversions = overrides.get("param_flag_inversions") or {}
    type_ovr = overrides.get("command_type_overrides") or {}

    def resolve(ep):
        oid = ep.operation_id
        o: dict = {"command_name": names.get(oid) or ep.command_name}
        if oid in skip:
            o["skip"] = True
            return o
        if oid in blocked:
            o["block"] = blocked[oid]
        if oid in warns:
            o["warn"] = warns[oid]
        ro = req_ovr.get(oid, {})
        if ro.get("multipart"):
            o["multipart"] = True
        if ro.get("content_type"):
            o["content_type"] = ro["content_type"]
        if oid in cli_names:
            o["param_cli_names"] = cli_names[oid]
        if oid in pagination:
            o["pagination"] = pagination[oid]
        if oid in list_keys:
            o["item_key"] = list_keys[oid]
        if oid in columns:
            o["table_columns"] = columns[oid]
        if oid in notes:
            o["help_notes"] = notes[oid]
        if out_file.get(oid):
            o["output_file_option"] = True
        if body_file.get(oid):
            o["body_from_file"] = True
        if oid in body_extra:
            o["body_fields_override"] = body_extra[oid]
        if oid in body_xf:
            o["body_transform"] = body_xf[oid]
        if oid in exit_codes:
            o["exit_code_from"] = exit_codes[oid]
        if oid in inversions:
            o["param_flag_inversions"] = inversions[oid]
        if oid in type_ovr:
            o["command_type"] = type_ovr[oid]
        return o

    return resolve


# ── group assembly ───────────────────────────────────────────────────────────

def _module_name(group: str) -> str:
    return group.replace("-", "_")


def build_group(group: str, source_tags: list, spec: dict, overrides: dict,
                resolve, seen: set) -> tuple[list, list]:
    """Parse a group's endpoints (across its source tags) + build manifest rows.

    Returns (kept_endpoints, manifest_rows). Skipped ops are dropped; blocked and
    warned ops are kept (as stub / warning command). Fails on a duplicate command
    name within the group (design § 5 collision lint)."""
    auto_inject = set(overrides.get("auto_inject_from_config") or ["orgId", "projectId"])
    endpoints: list = []
    for tag in source_tags:
        endpoints.extend(parse_tag(tag, spec, auto_inject=auto_inject, seen=seen))

    kept: list = []
    rows: list = []
    names_seen: dict = {}
    for ep in endpoints:
        o = resolve(ep)
        if o.get("skip"):
            continue
        cmd = o["command_name"]
        names_seen.setdefault(cmd, []).append(ep.operation_id)
        kept.append((ep, o))
        status = "blocked" if o.get("block") else ("warn" if o.get("warn") else "generated")
        non_inject_path = [v for v in ep.path_vars if v not in ep.auto_inject_path_params]
        required = ([f"<{v}>" for v in non_inject_path]
                    + [q.name for q in ep.query_params if q.required]
                    + [f.name for f in ep.body_fields if f.required])
        rows.append({
            "group": group,
            "command": cmd,
            "operationId": ep.operation_id,
            "method": ep.method,
            "path": ep.url_path,
            "read_only": ep.method == "GET" and status != "blocked",
            "required_params": required,
            "status": status,
        })
    dupes = {n: ids for n, ids in names_seen.items() if len(ids) > 1}
    if dupes:
        detail = "; ".join(f"{n} <- {ids}" for n, ids in dupes.items())
        raise SystemExit(f"Command-name collision in group '{group}': {detail}")
    return kept, rows


# ── emission ─────────────────────────────────────────────────────────────────

_REGISTRY_HEADER = '''"""Generated group registry — do NOT edit. Rewritten wholesale by
tools/generator/generate.py on every run. main.py mounts these via
wxcc_flow.generated.register(app)."""

GENERATED_GROUPS = [
'''


def _render_init(groups: list) -> str:
    modules = [_module_name(g) for g in groups]
    lines = [
        "# GENERATED by tools/generator — do not edit. Regenerate instead.",
        '"""The `wxcc-flow api <group> <op>` namespace (generated from the spec)."""',
        "import typer",
        "",
        "from wxcc_flow.generated import (",
    ]
    lines += [f"    {m}," for m in modules]
    lines += [
        ")",
        "",
        "_GROUPS = [",
    ]
    lines += [f'    ("{g}", {_module_name(g)}.app),' for g in groups]
    lines += [
        "]",
        "",
        "",
        "def register(app):",
        '    """Mount the generated `api` namespace onto the root typer app."""',
        '    api = typer.Typer(help="Raw 1:1 Flow Store API commands (generated).", no_args_is_help=True)',
        "    for name, sub in _GROUPS:",
        "        api.add_typer(sub, name=name)",
        '    app.add_typer(api, name="api")',
        "",
    ]
    return "\n".join(lines)


def emit(groups_data: list, output_dir: Path) -> None:
    """groups_data: list of (group, kept_endpoints, manifest_rows)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    group_names = [g for g, _k, _r in groups_data]
    manifest: list = []
    registry: list = []

    for group, kept, rows in groups_data:
        eps = [ep for ep, _o in kept]
        ovr_map = {id(ep): o for ep, o in kept}
        code = R.render_group_module(group, eps, lambda ep: ovr_map[id(ep)])
        (output_dir / f"{_module_name(group)}.py").write_text(code)
        registry.append((_module_name(group), group))
        manifest.extend(rows)

    (output_dir / "__init__.py").write_text(_render_init(group_names))

    reg_lines = [_REGISTRY_HEADER]
    reg_lines += [f'    ("{m}", "{g}"),\n' for m, g in registry]
    reg_lines += ["]\n"]
    (output_dir / "_registry.py").write_text("".join(reg_lines))

    (output_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


# ── CLI ──────────────────────────────────────────────────────────────────────

def _dry_run(groups_data: list) -> None:
    total = 0
    for group, kept, rows in groups_data:
        print(f"\n{'='*64}\n  {group}  ({len(kept)} commands)\n{'='*64}")
        for ep, o in kept:
            tag = ""
            if o.get("block"):
                tag = "  [BLOCKED]"
            elif o.get("warn"):
                tag = "  [warn]"
            elif o.get("multipart"):
                tag = "  [multipart]"
            elif o.get("pagination"):
                tag = "  [paginate]"
            print(f"  {o['command_name']:22s} {ep.method:6s} {ep.command_type:8s} {ep.operation_id}{tag}")
            total += 1
    print(f"\nTotal: {len(groups_data)} groups, {total} commands")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate wxcc-flow api commands from the Flow Store spec")
    ap.add_argument("--all", action="store_true", help="Generate all groups")
    ap.add_argument("--group", help="Generate a single group")
    ap.add_argument("--list-groups", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--spec", default=str(DEFAULT_SPEC))
    ap.add_argument("--overrides", default=str(DEFAULT_OVERRIDES))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = ap.parse_args(argv)

    if not Path(args.spec).exists():
        print(f"Spec not found: {args.spec}", file=sys.stderr)
        return 1
    spec = load_spec(args.spec)
    with open(args.overrides) as f:
        overrides = yaml.safe_load(f) or {}

    lint_overrides(overrides, spec)
    groups = overrides.get("groups") or {}

    if args.list_groups:
        for g, tags in groups.items():
            print(f"{g:24s} <- {', '.join(tags)}")
        return 0

    targets = list(groups.keys()) if args.all else ([args.group] if args.group else [])
    if not targets:
        ap.print_help()
        return 0
    if args.group and args.group not in groups:
        print(f"Unknown group: {args.group}", file=sys.stderr)
        return 1

    resolve = build_resolver(overrides)
    seen: set = set()
    groups_data: list = []
    for g in targets:
        kept, rows = build_group(g, groups[g], spec, overrides, resolve, seen)
        groups_data.append((g, kept, rows))

    if args.dry_run:
        _dry_run(groups_data)
        return 0

    emit(groups_data, Path(args.output))
    total = sum(len(k) for _g, k, _r in groups_data)
    print(f"Generated {len(groups_data)} groups, {total} commands → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
