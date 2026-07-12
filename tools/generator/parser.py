"""Parse the Flow Store OpenAPI 3.0 spec into normalized Endpoint dataclasses.

Fork of /webexCalling openapi_parser.py + postman_parser.py, merged and
retargeted to a single spec. Fork fixes (design § 3b):
  #1  _safe_param_name sanitizes spaces / non-identifier chars (spaced params
      like "Flow Type" were a SyntaxError in wxcli).
  #2  auto-inject matches path AND query params case-insensitively.
  #5  integer/number/boolean params carry a typed field_type (int/float/bool);
      the renderer emits typed typer.Options instead of str-everywhere.
  #7  ops without an operationId dedup on (method, path) instead of never.
  #8  spec-declared `force` params are typed bool (see renderer).
  #9  allOf is merged in request-body schemas (wxcli merged it only on responses).
Capability 1: paths are emitted spec-literal — the wxcli leading-`v1/` strip is
gone; url_path keeps the leading slash so emitted code calls c.get("/...").
Multipart is NOT hard-skipped here (wxcli dropped multipart ops); it is forced
per-op via the renderer's request_overrides.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── dataclasses (merged from postman_parser.py) ──────────────────────────────

@dataclass
class EndpointField:
    name: str            # wire name, verbatim from spec (e.g. "flowType", "Flow Type")
    python_name: str     # safe Python identifier (e.g. "flow_type")
    cli_flag: str        # CLI flag stem without leading -- (e.g. "flow-type")
    field_type: str      # str | int | float | bool | array | object
    description: str
    required: bool = False
    enum_values: list | None = None


@dataclass
class Endpoint:
    operation_id: str
    name: str                    # summary or operationId (for docstring)
    method: str
    url_path: str                # spec-literal path, leading slash kept
    path_vars: list              # ordered path param wire names
    query_params: list           # list[EndpointField]
    body_fields: list            # list[EndpointField]
    command_type: str
    command_name: str
    raw_path: list = field(default_factory=list)
    response_list_key: str | None = None
    response_id_key: str | None = None
    deprecated: bool = False
    json_body_example: str | None = None
    auto_inject_path_params: list = field(default_factory=list)   # orgId/projectId in path
    auto_inject_query_params: list = field(default_factory=list)  # orgId/projectId in query
    has_request_body: bool = False
    request_content_type: str | None = None   # spec-declared body content type (informational)
    tag: str = ""


# ── name derivation ──────────────────────────────────────────────────────────

PYTHON_KEYWORDS = {
    "list", "type", "id", "format", "input", "print", "open", "set", "map", "filter",
    "from", "import", "class", "def", "return", "yield", "for", "while", "if", "else",
    "elif", "try", "except", "finally", "with", "as", "pass", "break", "continue",
    "and", "or", "not", "in", "is", "lambda", "global", "nonlocal", "del", "raise",
    "assert", "True", "False", "None", "async", "await", "all", "any", "str", "int",
}


def _snake(name: str) -> str:
    """camelCase / spaced / punctuated → snake_case identifier body."""
    s = name.lstrip("$")
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s)               # non-alnum runs → _
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)   # ACRONYMWord → ACRONYM_Word
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)       # camelCase → camel_Case
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s


def _flag(name: str) -> str:
    """Wire name → CLI flag stem (dash-separated), e.g. 'Flow Type' → 'flow-type'."""
    return (_snake(name) or "arg").replace("_", "-")  # floor: never emit an empty '--' flag


def _safe_param_name(name: str) -> str:
    """Fork fix #1: produce a valid, non-colliding Python identifier."""
    snake = _snake(name)
    if not snake:
        snake = "arg"
    if snake[0].isdigit():
        snake = "p_" + snake
    if snake in PYTHON_KEYWORDS:
        snake = snake + "_param"
    return snake


# backward-compat aliases used by a couple of helpers
camel_to_snake = _snake


def _safe_func_name(command_name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", command_name.replace("-", "_"))
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or name[0].isdigit():
        name = "cmd_" + name
    if name in PYTHON_KEYWORDS:
        return f"cmd_{name}"
    return name


def _make_field(wire_name: str, field_type: str, description: str,
                required: bool, enum_values) -> EndpointField:
    return EndpointField(
        name=wire_name,
        python_name=_safe_param_name(wire_name),
        cli_flag=_flag(wire_name),
        field_type=field_type,
        description=(description or "")[:120],
        required=required,
        enum_values=enum_values,
    )


# ── spec loading + ref resolution ────────────────────────────────────────────

def load_spec(path) -> dict:
    with open(path) as f:
        return json.load(f)


def resolve_ref(spec: dict, ref: str) -> dict:
    parts = ref.lstrip("#/").split("/")
    result = spec
    for part in parts:
        result = result[part]
    return result


def _merge_all_of(schema: dict, spec: dict) -> dict:
    """Merge an allOf schema into a single {type, properties, required}.

    Used for BOTH request and response bodies (fork fix #9 — wxcli merged allOf
    only on responses).
    """
    if "allOf" not in schema:
        return schema
    merged_props: dict = {}
    merged_required: list = []
    for item in schema["allOf"]:
        if "$ref" in item:
            item = resolve_ref(spec, item["$ref"])
        if "allOf" in item:                 # recurse: nested allOf / ref-to-allOf
            item = _merge_all_of(item, spec)
        merged_props.update(item.get("properties", {}))
        merged_required.extend(item.get("required", []))
    return {"type": "object", "properties": merged_props, "required": merged_required}


def _openapi_type(schema: dict) -> str:
    t = schema.get("type", "string")
    if t == "integer":
        return "int"
    if t == "number":
        return "float"
    if t == "boolean":
        return "bool"
    if t == "array":
        return "array"
    if t == "object":
        return "object"
    return "str"


def _json_content(content: dict) -> dict:
    return (
        content.get("application/json")
        or content.get("application/json;charset=UTF-8")
        or content.get("application/merge-patch+json")
        or content.get("application/json-patch+json")
        or {}
    )


def _get_response_schema(op: dict, spec: dict, status_code: str = "200") -> dict | None:
    resp = op.get("responses", {}).get(status_code, {})
    schema = _json_content(resp.get("content", {})).get("schema", {})
    if not schema:
        return None
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])
    if "allOf" in schema:
        schema = _merge_all_of(schema, spec)
    return schema


# ── parameters ───────────────────────────────────────────────────────────────

def parse_parameters(params, spec, auto_inject: set | None = None):
    """Return (path_vars, query_params, auto_inject_path, auto_inject_query).

    auto_inject matching is CASE-INSENSITIVE for both path and query params
    (fork fix #2 — wxcli hardcoded the literal "orgId" on the query side).
    """
    inject_lower = {a.lower() for a in (auto_inject or set())}
    path_vars: list = []
    query_params: list = []
    auto_inject_path: list = []
    auto_inject_query: list = []

    for param in params:
        if "$ref" in param:
            param = resolve_ref(spec, param["$ref"])
        name = param.get("name", "")
        location = param.get("in", "")
        schema = param.get("schema", {})
        if location == "path":
            path_vars.append(name)
            if name.lower() in inject_lower:
                auto_inject_path.append(name)
        elif location == "query":
            if name.lower() in inject_lower:
                auto_inject_query.append(name)
                continue
            query_params.append(_make_field(
                name, _openapi_type(schema), param.get("description", ""),
                param.get("required", False), schema.get("enum"),
            ))
    return path_vars, query_params, auto_inject_path, auto_inject_query


# ── request body ─────────────────────────────────────────────────────────────

def _schema_to_example(schema: dict, spec: dict, depth: int = 0) -> Any:
    if depth > 2:
        return "..."
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])
    if "allOf" in schema:
        schema = _merge_all_of(schema, spec)
    t = schema.get("type", "object")
    if t == "string":
        enum = schema.get("enum")
        return enum[0] if enum else "..."
    if t in ("integer", "number"):
        return 0
    if t == "boolean":
        return True
    if t == "array":
        return [_schema_to_example(schema.get("items", {}), spec, depth + 1)]
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        ordered = [k for k in props if k in required] + [k for k in props if k not in required]
        result = {}
        for nm in ordered[:8]:
            prop = props[nm]
            if "$ref" in prop:
                prop = resolve_ref(spec, prop["$ref"])
            result[nm] = _schema_to_example(prop, spec, depth + 1)
        return result
    return "..."


def _request_schema(op: dict, spec: dict) -> tuple[dict, str | None, bool]:
    """Return (resolved_schema, content_type, has_body)."""
    rb = op.get("requestBody", {})
    content = rb.get("content", {})
    if not content:
        return {}, None, False
    ct = None
    for candidate in ("application/json", "application/json;charset=UTF-8",
                      "application/merge-patch+json", "application/json-patch+json"):
        if candidate in content:
            ct = candidate
            break
    if ct is None:
        ct = next(iter(content.keys()))
    schema = content.get(ct, {}).get("schema", {})
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])
    if "allOf" in schema:
        schema = _merge_all_of(schema, spec)
    return schema, ct, True


def parse_request_body(op: dict, spec: dict) -> list:
    schema, _ct, has_body = _request_schema(op, spec)
    if not has_body:
        return []
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    fields: list = []
    for name, prop in properties.items():
        if "$ref" in prop:
            resolved = resolve_ref(spec, prop["$ref"])
            if resolved.get("type") in ("string", "integer", "number", "boolean"):
                prop = {**resolved, "description": prop.get("description") or resolved.get("description", "")}
            else:
                fields.append(_make_field(name, "object", prop.get("description", ""),
                                          name in required_fields, None))
                continue
        fields.append(_make_field(name, _openapi_type(prop), prop.get("description", ""),
                                  name in required_fields, prop.get("enum")))
    return fields


def generate_body_example(op: dict, spec: dict) -> str | None:
    schema, _ct, has_body = _request_schema(op, spec)
    if not has_body:
        return None
    props = schema.get("properties", {})
    has_nested = any(p.get("type") in ("object", "array") or "$ref" in p for p in props.values())
    if not has_nested:
        return None
    return json.dumps(_schema_to_example(schema, spec), separators=(",", ":"))


# ── command-type detection + response keys ───────────────────────────────────

def detect_command_type(method: str, path: str, op: dict, spec: dict) -> str:
    method = method.upper()
    segments = path.rstrip("/").split("/")
    last = segments[-1] if segments else ""
    if method == "POST" and ("actions" in segments or "invoke" in segments):
        return "action"
    if method == "POST":
        return "create"
    if method in ("PUT", "PATCH"):
        return "update"
    if method == "DELETE":
        return "delete"
    if method == "GET":
        if last.startswith("{") and last.endswith("}"):
            return "show"
        if last == "me":
            return "show"
        schema = _get_response_schema(op, spec, "200")
        if schema:
            if schema.get("type") == "array":
                return "list"
            if any(p.get("type") == "array" for p in schema.get("properties", {}).values()):
                return "list"
            return "show"
        return "list"
    return "action"


def extract_response_list_key(op: dict, spec: dict) -> str | None:
    schema = _get_response_schema(op, spec, "200")
    if not schema or schema.get("type") == "array":
        return None
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    arrays = [n for n, p in props.items() if p.get("type") == "array"]
    if not arrays:
        return None
    if len(arrays) == 1:
        return arrays[0]
    req_arrays = [a for a in arrays if a in required]
    return req_arrays[0] if req_arrays else arrays[0]


def extract_response_id_key(op: dict, spec: dict) -> str | None:
    schema = _get_response_schema(op, spec, "201") or _get_response_schema(op, spec, "200")
    if not schema:
        return None
    props = schema.get("properties", {})
    if not props:
        return None
    if "id" in props:
        return "id"
    for name in props:
        if name.endswith("Id"):
            return name
    if len(props) == 1:
        return list(props.keys())[0]
    return None


# ── path helpers ─────────────────────────────────────────────────────────────

def _path_to_raw_path(path: str) -> list:
    """'/foo/{bar}/baz:act' → ['foo', ':bar', 'baz', 'act'] (for command naming)."""
    result = []
    for seg in path.strip("/").split("/"):
        if seg.startswith("{") and "}" in seg:
            close = seg.index("}")
            result.append(":" + seg[1:close])
            suffix = seg[close + 1:]
            if suffix.startswith(":") and len(suffix) > 1:
                result.append(suffix[1:])
        elif ":" in seg:
            base, action = seg.split(":", 1)
            if base:
                result.append(base)
            if action:
                result.append(action)
        else:
            result.append(seg)
    return result


def _path_to_url_path(path: str) -> str:
    """Capability 1: spec-literal. Keep the leading slash; NO v1 strip, NO param
    rename. The client prepends the base URL to this leading-slash path."""
    return path if path.startswith("/") else "/" + path


# ── command-name derivation + dedup ──────────────────────────────────────────

_NAME_STOPWORDS = {"config", "v1", "v2", "flows", "project", "flow"}


def _derive_command_name(command_type: str, raw_path: list, name: str, seen_types: dict) -> str:
    base = command_type.replace("settings-get", "show")
    if base == "action":
        words = re.sub(r"[^a-zA-Z0-9 ]", " ", name).lower().split()
        return "-".join(words[:3]) or "action"
    count = seen_types.get(base, 0)
    seen_types[base] = count + 1
    if count == 0:
        return base
    for seg in reversed(raw_path):
        if not seg.startswith(":") and seg.lower() not in _NAME_STOPWORDS:
            suffix = _flag(seg).strip("-")
            if suffix:
                return f"{base}-{suffix}"
    return f"{base}-{count}"


def _dedup_command_names(endpoints: list) -> None:
    from collections import Counter
    counts = Counter(ep.command_name for ep in endpoints)
    dupes = {n for n, c in counts.items() if c > 1}
    for ep in endpoints:
        if ep.command_name not in dupes:
            continue
        for seg in reversed(ep.raw_path):
            if seg.startswith(":"):
                continue
            cand = _flag(seg).strip("-")
            if cand and cand not in ep.command_name:
                ep.command_name = f"{ep.command_name}-{cand}"
                break
    counts = Counter(ep.command_name for ep in endpoints)
    dupes = {n for n, c in counts.items() if c > 1}
    seen: dict = {}
    for ep in endpoints:
        if ep.command_name in dupes:
            n = seen.get(ep.command_name, 0)
            seen[ep.command_name] = n + 1
            if n > 0:
                ep.command_name = f"{ep.command_name}-{n}"


# ── operation + tag parsing ──────────────────────────────────────────────────

def parse_operation(method: str, path: str, op: dict, spec: dict,
                    auto_inject: set | None = None) -> Endpoint:
    params = op.get("parameters", [])
    path_vars, query_params, ai_path, ai_query = parse_parameters(params, spec, auto_inject)
    body_fields = parse_request_body(op, spec)
    _schema, req_ct, has_body = _request_schema(op, spec)
    command_type = detect_command_type(method, path, op, spec)
    response_list_key = extract_response_list_key(op, spec) if command_type == "list" else None
    response_id_key = extract_response_id_key(op, spec) if command_type == "create" else None
    json_body_example = (generate_body_example(op, spec)
                         if command_type in ("create", "update", "action") else None)
    return Endpoint(
        operation_id=op.get("operationId", ""),
        name=op.get("summary") or op.get("operationId", ""),
        method=method.upper(),
        url_path=_path_to_url_path(path),
        path_vars=path_vars,
        query_params=query_params,
        body_fields=body_fields,
        command_type=command_type,
        command_name="",
        raw_path=_path_to_raw_path(path),
        response_list_key=response_list_key,
        response_id_key=response_id_key,
        deprecated=op.get("deprecated", False),
        json_body_example=json_body_example,
        auto_inject_path_params=ai_path,
        auto_inject_query_params=ai_query,
        has_request_body=has_body,
        request_content_type=req_ct,
    )


_METHODS = ("get", "post", "put", "patch", "delete")


def parse_tag(tag: str, spec: dict, auto_inject: set | None = None,
              seen: set | None = None) -> list:
    """Parse every operation carrying `tag` into an Endpoint list.

    Dedup key is (operationId, path), falling back to (method, path) for ops
    with no operationId (fork fix #7). Command names are derived and deduped.
    Multipart is NOT skipped (fork removes wxcli's hard-skip); the renderer
    forces multipart per-op via request_overrides.
    """
    if seen is None:
        seen = set()
    endpoints: list = []
    seen_types: dict = {}
    for path, path_obj in spec.get("paths", {}).items():
        for method in _METHODS:
            op = path_obj.get(method)
            if not op or not isinstance(op, dict):
                continue
            if tag not in op.get("tags", []):
                continue
            op_id = op.get("operationId", "")
            dedup_key = (op_id, path) if op_id else (method, path)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            # merge path-level params (OpenAPI 3.0 §8.1)
            path_params = path_obj.get("parameters", [])
            op_params = op.get("parameters", [])
            if path_params:
                op_keys = {(p.get("name"), p.get("in")) for p in op_params}
                merged = [p for p in path_params
                          if (p.get("name"), p.get("in")) not in op_keys] + op_params
                op = {**op, "parameters": merged}
            ep = parse_operation(method, path, op, spec, auto_inject)
            ep.tag = tag
            ep.command_name = _derive_command_name(ep.command_type, ep.raw_path, ep.name, seen_types)
            endpoints.append(ep)
    _dedup_command_names(endpoints)
    return endpoints


def get_tags(spec: dict) -> list:
    tags: set = set()
    for path_obj in spec.get("paths", {}).values():
        for method in _METHODS:
            op = path_obj.get(method)
            if op and isinstance(op, dict):
                for tag in op.get("tags", []):
                    tags.add(tag)
    return sorted(tags)
