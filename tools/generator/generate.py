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
import ast
import copy
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
    "body_fields_override", "body_transform", "exit_code_from", "body_defaults",
    "param_flag_inversions", "command_type_overrides", "top_level_commands",
    "extra_commands", "auto_resolve_params",
    # Phase-B polish features (design 2026-07-12 "full polish"):
    "promote_to_argument", "success_echo", "expose_path_param",
    # Phase-C parity features:
    "param_defaults", "body_positional_list", "confirm_message", "require_some_body",
)

# Keys an extra_commands entry may set in its `overrides` block. These are the
# RESOLVED per-command keys the renderer reads (e.g. `warn`, `item_key`,
# `command_type`) — not the YAML top-level section names. A None/False value
# clears the key inherited from the base op.
_EXTRA_OVERRIDE_KEYS = {
    "param_cli_names", "promote_to_argument", "success_echo", "expose_path_param",
    "pagination", "item_key", "table_columns", "help_notes", "output_file_option",
    "body_from_file", "body_fields_override", "body_transform", "exit_code_from",
    "param_flag_inversions", "command_type", "body_defaults", "warn", "multipart",
    "content_type", "auto_resolve", "param_defaults", "body_positional_list",
    "confirm_message", "require_some_body",
}

# Non-opId-keyed top-level sections. Any top-level key not here or in
# _OPID_SECTIONS is a typo/unknown and fails the lint (so a mistyped section name
# — e.g. skip_endpoint — can never silently drop its whole payload).
_OTHER_SECTIONS = {"groups", "auto_inject_from_config", "skip_tags", "keep_endpoints",
                   "global_param_cli_names"}


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
    # unknown/typo'd top-level section names (design § 6 lint — a mistyped section
    # would otherwise silently drop its entire payload, e.g. re-exposing skips)
    recognized = _OTHER_SECTIONS | set(_OPID_SECTIONS)
    for key in overrides:
        if key not in recognized:
            errors.append(f"unknown top-level override section {key!r} "
                          f"(typo? recognized: {', '.join(sorted(recognized))})")
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
    # auto_resolve_params: each target must be a declared query param of the op
    for oid, specs in (overrides.get("auto_resolve_params") or {}).items():
        op = ops.get(oid)
        if op is None:
            continue   # already reported above
        declared = {p.get("name") for p in op.get("parameters", []) if p.get("in") == "query"}
        for pname, rspec in (specs or {}).items():
            if pname not in declared:
                errors.append(f"auto_resolve_params.{oid}: {pname!r} is not a query param of the op")
            if not isinstance(rspec, dict) or "field" not in rspec:
                errors.append(f"auto_resolve_params.{oid}.{pname}: needs a 'field' key")
            else:
                unknown = set(rspec) - {"field", "unwrap", "forward_params"}
                if unknown:
                    errors.append(f"auto_resolve_params.{oid}.{pname}: unknown keys {sorted(unknown)}")
    # extra_commands: entries need a name; overrides limited to resolved keys
    for oid, entries in (overrides.get("extra_commands") or {}).items():
        for i, entry in enumerate(entries or []):
            if not isinstance(entry, dict) or not entry.get("name"):
                errors.append(f"extra_commands.{oid}[{i}]: needs a 'name' key")
                continue
            unknown = set(entry) - {"name", "top_level", "doc", "overrides"}
            if unknown:
                errors.append(f"extra_commands.{oid}[{i}]: unknown keys {sorted(unknown)}")
            bad = set(entry.get("overrides") or {}) - _EXTRA_OVERRIDE_KEYS
            if bad:
                errors.append(f"extra_commands.{oid}[{i}].overrides: unknown keys {sorted(bad)} "
                              f"(use RESOLVED key names, e.g. warn/item_key/command_type)")
    # body_positional_list: needs an arg name
    for oid, bspec in (overrides.get("body_positional_list") or {}).items():
        if not isinstance(bspec, dict) or not bspec.get("arg"):
            errors.append(f"body_positional_list.{oid}: needs an 'arg' key")
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
    body_defaults = overrides.get("body_defaults") or {}
    global_cli = overrides.get("global_param_cli_names") or {}
    promote_arg = overrides.get("promote_to_argument") or {}
    success_echo = overrides.get("success_echo") or {}
    expose_path = overrides.get("expose_path_param") or {}
    auto_resolve = overrides.get("auto_resolve_params") or {}
    param_dflts = overrides.get("param_defaults") or {}
    body_pos = overrides.get("body_positional_list") or {}
    confirm_msg = overrides.get("confirm_message") or {}
    require_body = overrides.get("require_some_body") or {}

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
        # global flag renames (e.g. flowType/"Flow Type" → --type) apply to every
        # op; a per-op param_cli_names entry wins on a conflicting wire name.
        merged_cli = {**global_cli, **cli_names.get(oid, {})}
        if merged_cli:
            o["param_cli_names"] = merged_cli
        if oid in promote_arg:
            o["promote_to_argument"] = promote_arg[oid]
        if oid in success_echo:
            o["success_echo"] = success_echo[oid]
        if oid in expose_path:
            o["expose_path_param"] = expose_path[oid]
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
        if oid in body_defaults:
            o["body_defaults"] = body_defaults[oid]
        if oid in auto_resolve:
            o["auto_resolve"] = auto_resolve[oid]
        if oid in param_dflts:
            o["param_defaults"] = param_dflts[oid]
        if oid in body_pos:
            o["body_positional_list"] = body_pos[oid]
        if oid in confirm_msg:
            o["confirm_message"] = confirm_msg[oid]
        if require_body.get(oid):
            o["require_some_body"] = True
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
    extras_by_op = overrides.get("extra_commands") or {}
    endpoints: list = []
    for tag in source_tags:
        endpoints.extend(parse_tag(tag, spec, auto_inject=auto_inject, seen=seen))

    def _row(ep, o, cmd, status, extra=False):
        non_inject_path = [v for v in ep.path_vars if v not in ep.auto_inject_path_params]
        required = ([f"<{v}>" for v in non_inject_path]
                    + [q.name for q in ep.query_params if q.required]
                    + [f.name for f in ep.body_fields if f.required])
        row = {
            "group": group,
            "command": cmd,
            "operationId": ep.operation_id,
            "method": ep.method,
            "path": ep.url_path,
            "read_only": ep.method == "GET" and status != "blocked",
            "required_params": required,
            "status": status,
        }
        if extra:
            row["extra"] = True
        return row

    kept: list = []
    rows: list = []
    names_seen: dict = {}
    for ep in endpoints:
        o = resolve(ep)
        extras = extras_by_op.get(ep.operation_id) or []
        if o.get("skip"):
            if extras:
                raise SystemExit(f"extra_commands: {ep.operation_id!r} is skipped — cannot clone it")
            continue
        cmd = o["command_name"]
        names_seen.setdefault(cmd, []).append(ep.operation_id)
        kept.append((ep, o))
        status = "blocked" if o.get("block") else ("warn" if o.get("warn") else "generated")
        rows.append(_row(ep, o, cmd, status))
        if extras and status == "blocked":
            raise SystemExit(f"extra_commands: {ep.operation_id!r} is a blocked stub — cannot clone it")
        # extra_commands: clone the op into additional commands. The clone starts
        # from the base's RESOLVED overrides; the entry's `overrides` block is laid
        # on top (a None/False value clears the inherited key).
        for entry in extras:
            ep2 = copy.deepcopy(ep)
            if entry.get("doc"):
                ep2.name = entry["doc"]
            o2 = dict(o)
            o2["command_name"] = entry["name"]
            o2.update(entry.get("overrides") or {})
            names_seen.setdefault(entry["name"], []).append(f'{ep.operation_id}+extra')
            kept.append((ep2, o2))
            status2 = "warn" if o2.get("warn") else "generated"
            rows.append(_row(ep2, o2, entry["name"], status2, extra=True))
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


def _render_init(groups: list, promotions: list) -> str:
    modules = [_module_name(g) for g in groups]
    lines = [
        "# GENERATED by tools/generator — do not edit. Regenerate instead.",
        '"""The `wxcc-flow api <group> <op>` namespace (generated from the spec)."""',
        "import typer",
        "from typer.main import get_command_name",
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
        "# (group_cli_name, api_command_name, top_level_name): a generated command",
        "# ALSO registered at the root app under its documented porcelain name",
        "# (design § 5). Promotion REQUIRES the hand-written command of that name to",
        "# be deleted — register() raises if one is still present.",
        "_PROMOTIONS = [",
    ]
    lines += [f'    ("{g}", "{a}", "{t}"),' for g, a, t in promotions]
    lines += [
        "]",
        "",
        "",
        "def _effective_name(ci):",
        '    """The command name typer will expose (mirrors typer\'s own derivation)."""',
        "    return get_command_name(ci.name or ci.callback.__name__)",
        "",
        "",
        "def register(app):",
        '    """Mount the generated `api` namespace, then promote the § 5 commands to root."""',
        '    api = typer.Typer(help="Raw 1:1 Flow Store API commands (generated).", no_args_is_help=True)',
        "    for name, sub in _GROUPS:",
        "        api.add_typer(sub, name=name)",
        '    app.add_typer(api, name="api")',
        "    _subs = dict(_GROUPS)",
        "    existing = {_effective_name(ci) for ci in app.registered_commands}",
        "    for group, api_cmd, top_name in _PROMOTIONS:",
        "        if top_name in existing:",
        "            raise RuntimeError(",
        "                f\"wxcc-flow: generated command '{top_name}' collides with a still-\"",
        "                f\"registered hand-written command. Delete the hand-written '{top_name}' \"",
        '                f"— promotion (design § 5) requires it.")',
        "        sub = _subs[group]",
        "        ci = next(c for c in sub.registered_commands if _effective_name(c) == api_cmd)",
        "        app.command(top_name)(ci.callback)",
        "        existing.add(top_name)",
        "",
    ]
    return "\n".join(lines)


def _build_promotions(overrides: dict, groups_data: list) -> list:
    """Resolve top_level_commands (opId → name) into (group, api_cmd, name) rows,
    validating each op is generated (not skipped/blocked) and each name is unique."""
    top_level = overrides.get("top_level_commands") or {}
    loc: dict = {}
    extra_loc: dict = {}
    for _g, _kept, rows in groups_data:
        for row in rows:
            if row.get("extra"):
                extra_loc[(row["operationId"], row["command"])] = (row["group"], row["command"])
            else:
                loc[row["operationId"]] = (row["group"], row["command"], row["status"])
    promotions: list = []
    errors: list = []
    by_name: dict = {}
    for oid, name in top_level.items():
        if oid not in loc:
            errors.append(f"{oid!r} is skipped or absent from the generated set — cannot promote")
            continue
        group, cmd, status = loc[oid]
        if status == "blocked":
            errors.append(f"{oid!r} is a blocked stub — cannot promote")
            continue
        if name in by_name:
            errors.append(f"name {name!r} promoted twice ({by_name[name]} and {oid})")
            continue
        by_name[name] = oid
        promotions.append((group, cmd, name))
    # extra_commands entries promote via their own top_level key (the base opId
    # already maps to the base command in top_level_commands, so it can't carry two)
    for oid, entries in (overrides.get("extra_commands") or {}).items():
        for entry in entries or []:
            name = entry.get("top_level")
            if not name:
                continue
            key = (oid, entry.get("name"))
            if key not in extra_loc:
                errors.append(f"extra_commands.{oid}: {entry.get('name')!r} not in the generated set — cannot promote")
                continue
            if name in by_name:
                errors.append(f"name {name!r} promoted twice ({by_name[name]} and {oid}+extra)")
                continue
            by_name[name] = f"{oid}+extra"
            group, cmd = extra_loc[key]
            promotions.append((group, cmd, name))
    if errors:
        raise SystemExit("top_level_commands lint FAILED:\n  - " + "\n  - ".join(errors))
    return promotions


def emit(groups_data: list, output_dir: Path, promotions: list) -> None:
    """groups_data: list of (group, kept_endpoints, manifest_rows)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    group_names = [g for g, _k, _r in groups_data]
    manifest: list = []
    registry: list = []

    for group, kept, rows in groups_data:
        eps = [ep for ep, _o in kept]
        ovr_map = {id(ep): o for ep, o in kept}
        code = R.render_group_module(group, eps, lambda ep: ovr_map[id(ep)])
        try:
            ast.parse(code)   # fail generation, not the CLI at import, on any collision/syntax error
        except SyntaxError as e:
            raise SystemExit(
                f"Generated module '{group}' is not valid Python (line {e.lineno}: {e.msg}). "
                f"Likely a parameter-name collision — fix via param_cli_names/command_names in the overrides.")
        (output_dir / f"{_module_name(group)}.py").write_text(code)
        registry.append((_module_name(group), group))
        manifest.extend(rows)

    (output_dir / "__init__.py").write_text(_render_init(group_names, promotions))

    reg_lines = [_REGISTRY_HEADER]
    reg_lines += [f'    ("{m}", "{g}"),\n' for m, g in registry]
    reg_lines += ["]\n"]
    (output_dir / "_registry.py").write_text("".join(reg_lines))

    # annotate the manifest rows that are promoted to a top-level porcelain name
    # (drives the Phase-D parity gate: spec = api + promoted + skipped + excused).
    promo_by_loc = {(g, a): t for g, a, t in promotions}
    for row in manifest:
        top = promo_by_loc.get((row["group"], row["command"]))
        if top:
            row["top_level"] = top
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

    if args.all:
        targets = list(groups.keys())          # --all supersedes --group
    elif args.group:
        if args.group not in groups:
            print(f"Unknown group: {args.group}", file=sys.stderr)
            return 1
        if not args.dry_run:
            # emit() rewrites __init__/_registry/_manifest wholesale, so writing a
            # single group would orphan the other modules and shrink the package.
            print("Refusing to emit a single group (would rewrite the package down "
                  "to one group). Use --all to regenerate, or --dry-run to preview.",
                  file=sys.stderr)
            return 1
        targets = [args.group]
    else:
        ap.print_help()
        return 0

    resolve = build_resolver(overrides)
    seen: set = set()
    groups_data: list = []
    for g in targets:
        kept, rows = build_group(g, groups[g], spec, overrides, resolve, seen)
        groups_data.append((g, kept, rows))

    # Promotions need the full generated set to resolve opId → (group, command);
    # only build them when generating all groups (a single --group is dry-run only).
    promotions = _build_promotions(overrides, groups_data) if args.all else []

    if args.dry_run:
        _dry_run(groups_data)
        if promotions:
            print(f"\nTop-level promotions ({len(promotions)}):")
            for g, a, t in promotions:
                print(f"  {t:24s} <- api {g} {a}")
        return 0

    emit(groups_data, Path(args.output), promotions)
    total = sum(len(k) for _g, k, _r in groups_data)
    print(f"Generated {len(groups_data)} groups, {total} commands, "
          f"{len(promotions)} promotions → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
