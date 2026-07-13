"""Render Endpoint objects into wxcc-flow generated typer command modules.

Fork of /webexCalling command_renderer.py, retargeted to the wxcc_flow seams
(design § 4): emitted code imports FlowClient/FlowStoreError + print_json/
print_table, constructs `c = FlowClient(debug=debug)`, builds a spec-literal
path f-string (orgId/projectId → c.org_id/c.project_id), calls
c.get/post/put/patch/delete/delete_with_body/post_multipart, and wraps the call
in `try/except FlowStoreError`.

Capabilities (design § 2): spec-literal paths (1), multipart (2), spaced-param
flags (3), enum help text (4), blocked/warn stubs (5), page-number pagination
loops (6), manifest (8, in generate.py). Feature keys (design § 6):
output_file_option, body_from_file, body_transform, exit_code_from,
param_flag_inversions, body_fields_override, help_notes, param_cli_names.
Phase-C keys: auto_resolve (pre-fetch a query param from the op's own path),
param_defaults (seed params the server defaults differently), body_positional_list
(array body from one positional list arg), confirm_message (delete confirm text),
require_some_body (refuse an empty body).
Phase-D2 keys: param_help / global_param_help (help backfill for spec params
with no description — see _help_for for the precedence).
"""
from __future__ import annotations

import re

from .parser import Endpoint, EndpointField, _safe_func_name, _make_field


# ── small emit helpers ───────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def _enum_help(f: EndpointField, max_desc: int = 70) -> str:
    """Field help text; render enum choices inline (capability 4)."""
    if f.enum_values:
        seen: dict = {}
        for v in f.enum_values:
            k = str(v).lower()
            if k not in seen:
                seen[k] = v
        vals = list(seen.values())
        if len(vals) <= 12:
            return _esc("Choices: " + ", ".join(str(v) for v in vals))
    return _esc((f.description or "")[:max_desc])


def _py_type(field_type: str) -> str:
    return {"int": "int", "float": "float", "bool": "bool"}.get(field_type, "str")


def _url_expr(ep: Endpoint, op_ovr: dict | None = None) -> str:
    """Spec-literal path f-string body: {orgId}→{c.org_id}, {projectId}→
    {c.project_id}, other {param}→{snake}.

    orgId/projectId are substituted UNCONDITIONALLY by their literal path token —
    the spec is inconsistent about declaring them as path parameters (some ops
    omit projectId), so relying on the declared-param set left {projectId}
    unbound → NameError (caught by the Phase A read-only sweep).

    expose_path_param (design polish): an auto-injected orgId/projectId can be
    exposed as an optional CLI override — the URL then reads a `_org_id`/
    `_project_id` local (declared in the body as `<flag> or c.<attr>`) so e.g.
    `connector-list --project-id <user-project>` can reach a project the
    connector-controller actually serves (the system project 404s)."""
    from .parser import _safe_param_name
    exposed = {p.lower() for p in (op_ovr or {}).get("expose_path_param") or []}
    org_token = "{_org_id}" if "orgid" in exposed else "{c.org_id}"
    proj_token = "{_project_id}" if "projectid" in exposed else "{c.project_id}"
    expr = ep.url_path
    expr = re.sub(r"\{[oO]rg[iI]d\}", org_token, expr)
    expr = re.sub(r"\{[pP]roject[iI]d\}", proj_token, expr)
    for var in ep.path_vars:
        if var.lower() in ("orgid", "projectid"):
            continue
        expr = expr.replace("{" + var + "}", "{" + _safe_param_name(var) + "}")
    return expr


def _auto_inject_query_lines(ep: Endpoint) -> list:
    """Inject orgId/projectId query params from config (fork fix #2 — some ops,
    e.g. variable-mapping, declare a required orgId QUERY param that would
    otherwise be silently dropped)."""
    lines = []
    for var in ep.auto_inject_query_params:
        if var.lower() == "orgid":
            lines.append(f'    params["{var}"] = c.org_id')
        elif var.lower() == "projectid":
            lines.append(f'    params["{var}"] = c.project_id')
    return lines


def _path_arg_defs(ep: Endpoint) -> list:
    from .parser import _safe_param_name
    defs = []
    for var in ep.path_vars:
        if var in ep.auto_inject_path_params:
            continue
        defs.append(f'    {_safe_param_name(var)}: str = typer.Argument(..., help="{_esc(var)}"),')
    return defs


def _expose_path_defs(op_ovr: dict) -> list:
    """Signature Options for exposed auto-injected path params (--project-id/--org-id)."""
    defs = []
    for p in op_ovr.get("expose_path_param") or []:
        pl = p.lower()
        if pl == "projectid":
            defs.append('    project_id: str = typer.Option(None, "--project-id", '
                        'help="Project ID to target (default: the configured project)"),')
        elif pl == "orgid":
            defs.append('    org_id: str = typer.Option(None, "--org-id", '
                        'help="Org ID to target (default: the configured org)"),')
    return defs


def _expose_path_lines(op_ovr: dict) -> list:
    """Body locals resolving each exposed path param to its override-or-config value."""
    lines = []
    for p in op_ovr.get("expose_path_param") or []:
        pl = p.lower()
        if pl == "projectid":
            lines.append("    _project_id = project_id or c.project_id")
        elif pl == "orgid":
            lines.append("    _org_id = org_id or c.org_id")
    return lines


def _promoted_arg_defs(ep: Endpoint, op_ovr: dict) -> list:
    """promote_to_argument: render named query params as positional Arguments
    (the verb's subject reads better positionally than behind a required flag —
    e.g. `revert FLOW VERSION` not `revert FLOW --version-id VERSION`). Still
    sent as query params in the request."""
    by_name = {qp.name: qp for qp in ep.query_params}
    defs = []
    for name in op_ovr.get("promote_to_argument") or []:
        qp = by_name.get(name)
        if qp is None:
            continue
        defs.append(f'    {qp.python_name}: {_py_type(qp.field_type)} = '
                    f'typer.Argument(..., help="{_esc(qp.description or name)}"),')
    return defs


def _promoted_query_lines(ep: Endpoint, op_ovr: dict) -> list:
    """params-dict lines for promoted args (always sent — they are required)."""
    by_name = {qp.name: qp for qp in ep.query_params}
    lines = []
    for name in op_ovr.get("promote_to_argument") or []:
        qp = by_name.get(name)
        if qp is None:
            continue
        if qp.field_type == "bool":
            lines.append(f'    params["{qp.name}"] = str({qp.python_name}).lower()')
        else:
            lines.append(f'    params["{qp.name}"] = {qp.python_name}')
    return lines


def _param_default_lines(op_ovr: dict) -> list:
    """param_defaults: seed a query param the server defaults differently from
    the documented CLI behavior (e.g. export's --version must default to 'draft';
    the spec default is 'latest'). setdefault AFTER the query build so an
    explicit flag always wins."""
    return [f'    params.setdefault("{wire}", {val!r})'
            for wire, val in (op_ovr.get("param_defaults") or {}).items()]


def _auto_resolve_lines(ep: Endpoint, op_ovr: dict) -> list:
    """auto_resolve_params: when the named query param was not supplied, resolve
    it by GETting the op's OWN path first (e.g. saveDraft/patchDraft pre-fetch
    the draft and read `flow.version` into expectedVersion — optimistic-lock
    parity with the hand-written commands). forward_params lists wire params
    (already in `params`) to pass along on the pre-fetch."""
    lines = []
    for pname, rspec in (op_ovr.get("auto_resolve") or {}).items():
        fwd = rspec.get("forward_params") or []
        lines.append(f'    if "{pname}" not in params:')
        lines.append(f"        _rp = {{k: params[k] for k in {fwd!r} if k in params}}")
        lines.append("        try:")
        lines.append(f'            _pre = c.get(f"{_url_expr(ep, op_ovr)}", params=_rp)')
        lines += [
            "        except FlowStoreError as e:",
            '            typer.echo(f"Error {e.status_code}: {e.body}", err=True)',
            "            raise typer.Exit(1)",
        ]
        if rspec.get("unwrap"):
            lines.append("        if isinstance(_pre, dict):")
            lines.append(f'            _pre = _pre.get("{rspec["unwrap"]}", _pre)')
        lines.append(f'        params["{pname}"] = (_pre.get("{rspec["field"]}") or 0) '
                     f"if isinstance(_pre, dict) else 0")
    return lines


def _cli_flag_for(f: EndpointField, op_ovr: dict) -> str:
    """Resolve the CLI flag stem, honoring param_cli_names (capability 3)."""
    override = (op_ovr.get("param_cli_names") or {}).get(f.name)
    return override if override else f.cli_flag


def _help_for(f: EndpointField, op_ovr: dict) -> str:
    """Resolve a field's help text (Phase-D2 backfill). Precedence: per-op
    param_help (may override spec text) > spec text (description / enum
    choices) > global_param_help (fills only where the spec ships nothing)."""
    per_op = (op_ovr.get("param_help") or {}).get(f.name)
    if per_op:
        return _esc(per_op)
    spec_help = _enum_help(f)
    if spec_help:
        return spec_help
    return _esc((op_ovr.get("global_param_help") or {}).get(f.name) or "")


def _option_def(f: EndpointField, op_ovr: dict, required: bool | None = None) -> str:
    """Emit one typer.Option definition for a query/body field (typed scalars)."""
    flag = _cli_flag_for(f, op_ovr)
    pyt = _py_type(f.field_type)
    req = f.required if required is None else required
    help_text = _help_for(f, op_ovr)
    if f.field_type == "bool":
        return (f'    {f.python_name}: bool = typer.Option(None, "--{flag}/--no-{flag}", '
                f'help="{help_text}"),')
    default = "..." if req else "None"
    prefix = "(required) " if req else ""
    return (f'    {f.python_name}: {pyt} = typer.Option({default}, "--{flag}", '
            f'help="{_esc(prefix)}{help_text}"),')


def _query_build(ep: Endpoint, op_ovr: dict, exclude: set) -> list:
    """params-dict build lines for query params not otherwise handled."""
    lines = []
    for qp in ep.query_params:
        if qp.name in exclude:
            continue
        lines.append(f"    if {qp.python_name} is not None:")
        if qp.field_type == "bool":
            lines.append(f'        params["{qp.name}"] = str({qp.python_name}).lower()')
        else:
            lines.append(f'        params["{qp.name}"] = {qp.python_name}')
    return lines


def _docstring(ep: Endpoint, op_ovr: dict) -> str:
    doc = _esc(ep.name) or ep.operation_id
    note = op_ovr.get("help_notes")
    suffix = f" {_esc(note)}" if note else ""
    example = ""
    if ep.json_body_example and not op_ovr.get("body_from_file"):
        example = f"\\n\\nExample --json-body:\\n  '{_esc(ep.json_body_example)}'"
    return f'    """{doc}.{suffix} [operationId: {ep.operation_id}]{example}"""'


def _error_tail() -> list:
    return [
        "    except FlowStoreError as e:",
        '        typer.echo(f"Error {e.status_code}: {e.body}", err=True)',
        "        raise typer.Exit(1)",
    ]


def _warn_banner(op_ovr: dict) -> list:
    text = op_ovr.get("warn")
    if not text:
        return []
    return [f'    typer.echo("Warning: {_esc(text)}", err=True)']


# ── body handling ────────────────────────────────────────────────────────────

def _body_fields(ep: Endpoint, op_ovr: dict) -> list:
    """Effective body scalar fields (spec + body_fields_override), object/array excluded."""
    fields = list(ep.body_fields)
    for spec_extra in op_ovr.get("body_fields_override", []) or []:
        fields.append(_make_field(spec_extra["name"], spec_extra.get("type", "str"),
                                   spec_extra.get("desc", ""), spec_extra.get("required", False),
                                   spec_extra.get("enum")))
    used = {_safe_arg(v) for v in ep.path_vars if v not in ep.auto_inject_path_params}
    used |= {qp.python_name for qp in ep.query_params}
    return [f for f in fields if f.field_type not in ("object", "array") and f.python_name not in used]


def _safe_arg(var: str) -> str:
    from .parser import _safe_param_name
    return _safe_param_name(var)


def _body_option_defs(ep: Endpoint, op_ovr: dict) -> list:
    bpl = op_ovr.get("body_positional_list")
    if bpl:
        # body_positional_list: the whole request body is a JSON array built from
        # ONE positional list argument (e.g. `prefs-rm FLOW_ID NAME [NAME...]`).
        # Suppresses spec-derived body flags and --json-body.
        return [f'    {bpl["arg"]}: list[str] = typer.Argument(..., '
                f'help="{_esc(bpl.get("help", ""))}"),']
    if op_ovr.get("body_from_file"):
        return ['    body_file: str = typer.Argument(..., help="Path to JSON body file (or - for stdin)"),']
    defs = []
    for f in _body_fields(ep, op_ovr):
        # Body scalars are ALWAYS optional flags — a complete --json-body must be
        # able to supply them (design §8). Required-ness is enforced at runtime by
        # the _missing check (which validates the --json-body path too).
        defs.append(_option_def(f, op_ovr, required=False))
    defs.append('    json_body: str = typer.Option(None, "--json-body", help="Full JSON body (overrides flags)"),')
    return defs


def _body_build(ep: Endpoint, op_ovr: dict) -> list:
    body_defaults = op_ovr.get("body_defaults") or {}
    bpl = op_ovr.get("body_positional_list")
    if bpl:
        return [f"    body = list({bpl['arg']})"]
    if op_ovr.get("body_from_file"):
        lines = [
            '    if body_file == "-":',
            "        body = json.load(sys.stdin)",
            "    else:",
            "        try:",
            '            with open(body_file) as _bf:',
            "                body = json.load(_bf)",
            "        except FileNotFoundError:",
            '            typer.echo(f"Error: File not found: {body_file}", err=True)',
            "            raise typer.Exit(1)",
        ]
        if op_ovr.get("body_transform") == "json-string":
            lines.append("    body = json.dumps(body)")
        return lines
    lines = ["    if json_body is not None:", "        body = json.loads(json_body)",
             "    else:", "        body = {}"]
    required = []
    for f in _body_fields(ep, op_ovr):
        if f.required:
            required.append(f.name)
        lines.append(f"        if {f.python_name} is not None:")
        lines.append(f'            body["{f.name}"] = {f.python_name}')
    # body_defaults + required check apply to BOTH branches (4-space, after the
    # if/else) so --json-body callers are seeded and validated too (fork fix #3, #6).
    for key, val in body_defaults.items():
        lines.append(f"    body.setdefault({key!r}, {val!r})")
    if required:
        lines.append(f"    _missing = [k for k in {required!r} if k not in body or body[k] is None]")
        lines.append("    if _missing:")
        lines.append('        typer.echo("Error: Missing required fields: " + ", ".join(_missing), err=True)')
        lines.append("        raise typer.Exit(1)")
    if op_ovr.get("body_transform") == "json-string":
        lines.append("    body = json.dumps(body)")
    return lines


# ── output handling ──────────────────────────────────────────────────────────

def _output_option(default: str, listy: bool, op_ovr: dict) -> list:
    fmt = "table|json" if listy else "json"
    defs = [f'    output: str = typer.Option("{default}", "-o", "--output", help="Output format: {fmt}"),']
    if op_ovr.get("output_file_option"):
        defs.append('    out: str = typer.Option(None, "--out", help="Write response JSON to FILE"),')
    return defs


def _emit_output(op_ovr: dict, var: str, listy: bool, columns_repr: str) -> list:
    lines = []
    if op_ovr.get("output_file_option"):
        lines += [
            "    if out:",
            f'        with open(out, "w") as _of:',
            f"            import json as _json; _json.dump({var}, _of, indent=2, default=str)",
            f'        typer.echo(f"Wrote {{out}}")',
            "        return",
        ]
    ecf = op_ovr.get("exit_code_from")
    if listy:
        lines += [
            '    if output == "table":',
            f"        print_table({var}, columns={columns_repr}, limit=0)",
            "    else:",
            f"        print_json({var})",
        ]
    else:
        # success_echo: many mutations (lock/unlock/delete) return a trivial ack —
        # an empty body (→ bare `null`) or a bare `"OK"` string. Neither is useful
        # output, so print the friendly confirmation for those; a STRUCTURED body
        # (dict/list, e.g. revert's version list) is real data and still prints.
        se = op_ovr.get("success_echo")
        if se:
            lines += [
                f"    if {var} and not isinstance({var}, str):",
                f"        print_json({var})",
                "    else:",
                f'        typer.echo(f"{se}")',
            ]
        else:
            lines.append(f"    print_json({var})")
    if ecf:
        key = ecf["json_key"]
        cond = f'{var}.get("{key}")'
        if ecf.get("invert"):
            cond = f"not {cond}"
        lines += [
            f"    if isinstance({var}, dict) and {cond}:",
            "        raise typer.Exit(1)",
        ]
    return lines


# ── HTTP call assembly ───────────────────────────────────────────────────────

def _http_call(ep: Endpoint, op_ovr: dict, into: str = "data") -> list:
    """Emit the try/except HTTP call for non-list command types."""
    path_line = f'    _path = f"{_url_expr(ep, op_ovr)}"'
    ct = op_ovr.get("content_type") or ep.request_content_type or "application/json"
    if op_ovr.get("multipart"):
        return [path_line,
                "    try:",
                '        with open(file, "rb") as _fh:',
                "            _content = _fh.read()",
                "    except FileNotFoundError:",
                '        typer.echo(f"Error: File not found: {file}", err=True)',
                "        raise typer.Exit(1)",
                "    import os as _os",
                "    try:",
                f"        {into} = c.post_multipart(_path, _os.path.basename(file), _content, params=params)",
                *_error_tail()]
    m = ep.method
    if m == "GET":
        call = f"c.get(_path, params=params)"
    elif m == "POST":
        call = (f"c.post(_path, json_body=body, params=params)"
                if ep.has_request_body else "c.post(_path, params=params)")
    elif m == "PUT":
        call = "c.put(_path, json_body=body, params=params)"
    elif m == "PATCH":
        call = f'c.patch(_path, json_body=body, params=params, content_type="{ct}")'
    elif m == "DELETE":
        call = ("c.delete_with_body(_path, json_body=body)"
                if ep.has_request_body else "c.delete(_path, params=params)")
    else:
        call = "c.get(_path, params=params)"
    return [path_line, "    try:", f"        {into} = {call}", *_error_tail()]


def _blocked_stub(ep: Endpoint, op_ovr: dict) -> str:
    func = _safe_func_name(op_ovr["command_name"])
    reason = _esc(op_ovr["block"])
    return "\n".join([
        f'@app.command("{op_ovr["command_name"]}")',
        f"def {func}(",
        "    debug: bool = typer.Option(False, \"--debug\"),",
        "):",
        f'    """[BLOCKED] {reason} [operationId: {ep.operation_id}]"""',
        f'    typer.echo("{reason}", err=True)',
        "    raise typer.Exit(2)",
    ])


def _columns_repr(op_ovr: dict, ep: Endpoint) -> str:
    cols = op_ovr.get("table_columns")
    if cols:
        return repr([(c[0], c[1]) for c in cols])
    return '[("ID", "id"), ("Name", "name")]'


def _inversion_excludes(op_ovr: dict) -> set:
    return set((op_ovr.get("param_flag_inversions") or {}).keys())


def _pagination_excludes(op_ovr: dict) -> set:
    pg = op_ovr.get("pagination")
    return {pg["page_param"], pg["size_param"]} if pg else set()


def render_command(ep: Endpoint, op_ovr: dict) -> str:
    if op_ovr.get("block"):
        return _blocked_stub(ep, op_ovr)

    name = op_ovr["command_name"]
    func = _safe_func_name(name)
    # Flow Store response schemas are opaque ({type: object}) so list-vs-show
    # cannot be inferred from the spec — it is declared in the overrides via
    # pagination or table_columns (both carry a known item_key). Every other GET
    # renders as show (print_json of the full response — safe, no key guessing).
    listy = (bool(op_ovr.get("pagination")) or bool(op_ovr.get("table_columns"))
             or op_ovr.get("command_type") == "list")
    pg = op_ovr.get("pagination")
    inv = op_ovr.get("param_flag_inversions") or {}
    # promoted query params become positional Arguments; exclude them from the
    # normal Option loop + _query_build (they get their own signature + params lines).
    exclude = (_pagination_excludes(op_ovr) | _inversion_excludes(op_ovr)
               | set(op_ovr.get("promote_to_argument") or []))

    # A delete's spec `force` query param would collide with the confirmation
    # --force flag (duplicate function arg) — rename it to --server-force.
    if ep.command_type == "delete":
        for qp in ep.query_params:
            if qp.python_name == "force":
                qp.python_name = "server_force"
                qp.cli_flag = "server-force"

    # ---- signature ----
    params: list = []
    params += _path_arg_defs(ep)
    params += _promoted_arg_defs(ep, op_ovr)   # positional subjects (after path args)
    if op_ovr.get("multipart"):
        params.append('    file: str = typer.Argument(..., help="Path to the JSON file to upload"),')
    for qp in ep.query_params:
        if qp.name in exclude:
            continue
        params.append(_option_def(qp, op_ovr))
    params += _expose_path_defs(op_ovr)         # --project-id / --org-id overrides
    for wire, spec in inv.items():
        cli = spec["cli_name"]
        params.append(f'    {cli.replace("-", "_")}: bool = typer.Option(None, "--{cli}/--no-{cli}", help="Sets {wire}"),')
    if pg:
        params.append('    page: int = typer.Option(None, "--page", help="Fetch a single 0-based page. Omit to fetch all pages."),')
        params.append('    size: int = typer.Option(None, "--size", help="Page size (default 100 when fetching all)."),')
    body_bearing = ep.command_type in ("create", "update", "action") or (
        ep.command_type == "delete" and ep.has_request_body)
    if body_bearing and ep.has_request_body and not op_ovr.get("multipart"):
        params += _body_option_defs(ep, op_ovr)
    if ep.command_type == "delete":
        params.append('    force: bool = typer.Option(False, "--force", help="Skip the confirmation prompt"),')
    default_out = "table" if (listy and op_ovr.get("table_columns")) else "json"
    params += _output_option(default_out, listy, op_ovr)
    params.append('    debug: bool = typer.Option(False, "--debug"),')

    # ---- body ----
    lines = [f'@app.command("{name}")', f"def {func}("] + params + ["):", _docstring(ep, op_ovr)]
    lines += _warn_banner(op_ovr)
    if ep.command_type == "delete":
        cm = op_ovr.get("confirm_message")
        confirm_target = _safe_arg(ep.path_vars[-1]) if [v for v in ep.path_vars if v not in ep.auto_inject_path_params] else None
        if cm:
            lines += ["    if not force:", f'        typer.confirm(f"{cm}", abort=True)']
        elif confirm_target:
            lines += ["    if not force:", f'        typer.confirm(f"Delete {{{confirm_target}}}?", abort=True)']
        else:
            lines += ["    if not force:", '        typer.confirm("Delete this resource?", abort=True)']
    lines.append("    c = FlowClient(debug=debug)")
    lines += _expose_path_lines(op_ovr)         # _project_id = project_id or c.project_id
    lines.append("    params = {}")
    lines += _auto_inject_query_lines(ep)
    lines += _promoted_query_lines(ep, op_ovr)  # always-sent positional subjects
    lines += _query_build(ep, op_ovr, exclude)
    for wire, spec in inv.items():
        cli_py = spec["cli_name"].replace("-", "_")
        val = f"not {cli_py}" if spec.get("invert") else cli_py
        if "true_value" in spec:
            # value-mapped bool flag: the wire wants e.g. yes/no, not true/false
            # (findFlows_1 withDraftVersions silently ignores "true" — audit F1)
            tv, fv = spec["true_value"], spec.get("false_value", "")
            lines += [f"    if {cli_py} is not None:",
                      f'        params["{wire}"] = {tv!r} if {val} else {fv!r}']
        else:
            lines += [f"    if {cli_py} is not None:", f'        params["{wire}"] = str({val}).lower()']
    lines += _param_default_lines(op_ovr)

    if listy:
        lines += _auto_resolve_lines(ep, op_ovr)
        lines += _render_list_body(ep, op_ovr, pg)
        lines += _emit_output(op_ovr, "items", True, _columns_repr(op_ovr, ep))
        return "\n".join(lines)

    # body-bearing types fall through here

    if body_bearing and ep.has_request_body and not op_ovr.get("multipart"):
        lines += _body_build(ep, op_ovr)
        if op_ovr.get("require_some_body"):
            lines += [
                "    if not body:",
                '        typer.echo("Error: provide at least one field to set (see --help).", err=True)',
                "        raise typer.Exit(1)",
            ]
    # auto_resolve AFTER the body build so client-side guards (missing file,
    # empty body) fire before the pre-fetch network call (audit F5)
    lines += _auto_resolve_lines(ep, op_ovr)
    lines += _http_call(ep, op_ovr, into="data")
    if ep.command_type == "delete" and not ep.has_request_body:
        lines += _emit_output(op_ovr, "data", False, "")
    else:
        lines += _emit_output(op_ovr, "data", False, "")
    return "\n".join(lines)


def _render_list_body(ep: Endpoint, op_ovr: dict, pg: dict | None) -> list:
    key = op_ovr.get("item_key") or (pg or {}).get("item_key") or ep.response_list_key or "items"
    extract = (f'data if isinstance(data, list) else '
               f'data.get("{key}", data.get("items", data.get("data", [])))')
    path_line = f'    _path = f"{_url_expr(ep, op_ovr)}"'
    if not pg:
        return [path_line, "    try:", "        data = c.get(_path, params=params)", *_error_tail(),
                f"    items = {extract}"]
    pp, sp = pg["page_param"], pg["size_param"]
    return [
        path_line,
        "    try:",
        "        if page is not None:",
        f'            params["{pp}"] = page',
        "            if size is not None:",
        f'                params["{sp}"] = size',
        "            data = c.get(_path, params=params)",
        f"            items = {extract}",
        "        else:",
        "            _size = size if size is not None else 100",
        "            items = []",
        "            _page = 0",
        "            while True:",
        "                _p = dict(params)",
        f'                _p["{pp}"] = _page',
        f'                _p["{sp}"] = _size',
        "                data = c.get(_path, params=_p)",
        f"                batch = {extract}",
        "                items.extend(batch)",
        "                if len(batch) < _size:",
        "                    break",
        "                _page += 1",
        "                if _page > 100000:",   # runaway guard: a server that ignores
        "                    break",            # `size` must not spin forever
        *_error_tail(),
    ]


# ── module assembly ──────────────────────────────────────────────────────────

def render_group_module(group_cli_name: str, endpoints: list, resolve_ovr) -> str:
    """Render a full generated group module. `resolve_ovr(ep) -> op_ovr dict`."""
    rendered = []
    needs_table = False
    needs_sys = False
    for ep in endpoints:
        op_ovr = resolve_ovr(ep)
        if op_ovr.get("skip"):
            continue
        code = render_command(ep, op_ovr)
        if (op_ovr.get("pagination") or op_ovr.get("table_columns")
                or op_ovr.get("command_type") == "list"):
            needs_table = True
        if op_ovr.get("body_from_file"):
            needs_sys = True
        rendered.append(code)

    imports = [
        "# GENERATED by tools/generator — do not edit. Regenerate instead.",
        f'"""Generated `wxcc-flow api {group_cli_name}` commands (Flow Store API)."""',
        "import json",
    ]
    if needs_sys:
        imports.append("import sys")
    imports += [
        "import typer",
        "from wxcc_flow.client import FlowClient, FlowStoreError",
        ("from wxcc_flow.output import print_json, print_table"
         if needs_table else "from wxcc_flow.output import print_json"),
        "",
        f'app = typer.Typer(help="Flow Store {group_cli_name} operations (generated).", no_args_is_help=True)',
        "",
    ]
    return "\n".join(imports) + "\n\n" + "\n\n\n".join(rendered) + "\n"
