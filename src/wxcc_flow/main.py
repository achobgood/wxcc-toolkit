"""wxcc-flow — CLI for Cisco WxCC Flow Designer REST APIs."""
import json
import sys
from pathlib import Path

import typer

from wxcc_flow import __version__
from wxcc_flow.client import FlowClient
from wxcc_flow.config import (
    load_config, save_config, resolve_token, get_base_url, BASE_URL,
)
from rich.console import Console
from rich.table import Table

from wxcc_flow.output import print_json, print_table

app = typer.Typer(
    name="wxcc-flow",
    help="CLI for Cisco WxCC Flow Designer REST APIs.",
    no_args_is_help=True,
)


def _client(debug: bool = False) -> FlowClient:
    return FlowClient(debug=debug)


def _write_json(data, file_path: str) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    typer.echo(f"Saved to {file_path}")


def version_callback(value: bool):
    if value:
        typer.echo(f"wxcc-flow {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=version_callback, is_eager=True),
    no_update_check: bool = typer.Option(
        False, "--no-update-check",
        help="Skip the once-a-day PyPI update check for this run.",
    ),
):
    # Best-effort upgrade nudge; never let it break a real command.
    try:
        from wxcc_flow.update_check import maybe_notify_update
        maybe_notify_update(__version__, disabled=no_update_check)
    except Exception:
        pass


# ── Configure ────────────────────────────────────────────────────────

@app.command()
def configure(
    base_url: str = typer.Option(BASE_URL, "--base-url", help="Flow Store base URL"),
):
    """Save a Webex token and auto-resolve org ID."""
    import base64
    import httpx

    token = typer.prompt("Webex API token").strip()

    typer.echo("Validating token...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = httpx.get("https://webexapis.com/v1/people/me", headers=headers, timeout=30)
    if not resp.is_success:
        typer.echo(f"Error: Invalid token (HTTP {resp.status_code}).", err=True)
        raise typer.Exit(1)

    me = resp.json()
    display_name = me.get("displayName", "")
    email = (me.get("emails") or ["unknown"])[0]
    raw_org_id = me.get("orgId", "")

    # Decode base64 Spark ID to bare UUID
    try:
        padded = raw_org_id + "=" * (4 - len(raw_org_id) % 4) if len(raw_org_id) % 4 else raw_org_id
        decoded = base64.b64decode(padded).decode("utf-8")
        org_id = decoded.rsplit("/", 1)[-1]
    except Exception:
        org_id = raw_org_id

    save_config({
        "token": token,
        "org_id": org_id,
        "base_url": base_url,
    })
    typer.echo(f"Authenticated: {display_name} ({email})")
    typer.echo(f"Org: {org_id}")
    typer.echo(f"Token saved to ~/.wxcc-flow/config.json")
    typer.echo("Project ID will be resolved automatically on first use.")


@app.command("set-project")
def set_project(
    project_id: str = typer.Argument(..., help="Project ID to switch to"),
):
    """Manually set the project ID (overrides auto-detection)."""
    cfg = load_config()
    cfg["project_id"] = project_id
    save_config(cfg)
    typer.echo(f"Project set to: {project_id}")


# ── Activity helpers (shared by schema / events survivors) ──────────

def _find_activity_safe(client: FlowClient, name: str, flow_type: str = "FLOW"):
    """Find an activity by name, returning None if not found."""
    data = client.get(client.v2_activities(), params={"flowType": flow_type})
    if isinstance(data, list):
        for act in data:
            if isinstance(act, dict) and act.get("activityName") == name:
                return act
    elif isinstance(data, dict):
        for _cat, activity_list in data.items():
            if isinstance(activity_list, list):
                for act in activity_list:
                    if act.get("activityName") == name or act.get("name") == name:
                        return act
    return None


def _iter_inputs(act: dict, deep: bool = False):
    """Yield input dicts from either definition shape.

    Prod returns a flat `inputs` list (with nested `children`); legacy
    deployments returned `inputGroups`. With deep=True, children are
    yielded after their parent so callers see every field.
    """
    if act.get("inputGroups"):
        for ig in act["inputGroups"]:
            if ig.get("name") == "Decryption settings":
                continue
            yield from ig.get("inputs", [])
        return
    stack = list(act.get("inputs") or [])
    while stack:
        inp = stack.pop(0)
        yield inp
        if deep:
            stack = list(inp.get("children") or []) + stack


# ── Activity Registry ────────────────────────────────────────────────

@app.command()
def schema(
    activity: str = typer.Argument(..., help="Activity name"),
    output: str = typer.Option("table", "-o", "--output"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Build a FlowIR node template from the activity definition.

    Uses REAL property names from the definition's input fields (there
    is no /schema endpoint on prod; propertyHints names were wrong).
    """
    c = _client(debug)
    act = c.get_activity_definition(activity, flow_type=flow_type)

    if output == "json":
        print_json(act)
        return

    raw_group = act.get("group", "action")
    group = raw_group.get("name", str(raw_group)) if isinstance(raw_group, dict) else str(raw_group)
    # Prod definitions carry activityType directly; guess from the name
    # only when it's absent (legacy shape).
    activity_type = act.get("activityType")
    if not activity_type:
        end_activities = {"disconnect-contact", "end-subflow", "end"}
        if activity in end_activities:
            activity_type = "end"
        elif activity == "start":
            activity_type = "start"
        else:
            activity_type = "action"

    node_id = f"node-{activity.replace('-', '_')}"
    display_name = act.get("displayName", activity)

    # Import property names that differ from the activity definition names.
    # The definition API uses one name, but the import validator requires another.
    _IMPORT_FIELD_OVERRIDES = {
        "queue-contact": {
            "destination": ("queueId", "Queue UUID — import validator requires 'queueId', not 'destination'"),
        },
    }
    overrides = _IMPORT_FIELD_OVERRIDES.get(activity, {})

    # Build properties from required inputs
    properties = {"activityName": activity}
    conditional_props = {}
    seen_fields = set()
    warnings = []
    for inp in _iter_inputs(act):
        if not inp.get("required"):
            continue
        field_name = inp.get("name", "")
        if field_name in seen_fields:
            continue
        seen_fields.add(field_name)
        if field_name in overrides:
            import_name, note = overrides[field_name]
            warnings.append(f"  ⚠ '{field_name}' → '{import_name}': {note}")
            field_name = import_name
        default = inp.get("defaultValue")
        children = inp.get("children") or []
        if default not in (None, "", [], {}):
            if isinstance(default, str) and default.startswith('"') and default.endswith('"'):
                default = default[1:-1]
            val = default
        elif children:
            # object[] input: show one example element with its child fields
            val = [{ch.get("name", ""): f"<{ch.get('type', 'string')}>"
                    for ch in children}]
        else:
            val = f"<{inp.get('type', 'string')}>"
        show_cond = inp.get("showOnCondition")
        if show_cond:
            cond_str = f"{show_cond.get('name', '')} == {show_cond.get('value', '')}" if isinstance(show_cond, dict) else str(show_cond)
            conditional_props[field_name] = (val, cond_str)
        else:
            properties[field_name] = val

    # Build output ports (prod flat outputPorts, or legacy errorPathLinks)
    error_ports = []
    for p in act.get("outputPorts") or []:
        error_ports.append({
            "id": p.get("condition", ""),
            "displayName": p.get("label", "")
                or ("error path" if p.get("isErrorPath") else ""),
        })
    for link in (act.get("shapeProperties") or {}).get("errorPathLinks", []):
        error_ports.append({
            "id": link.get("id", ""),
            "displayName": link.get("displayName", ""),
        })

    # Print node template
    console = Console()
    console.print(f"[bold]FlowIR Node Template for: {activity}[/bold]")
    console.print()
    template = {
        "id": node_id,
        "name": display_name,
        "activityType": activity_type,
        "group": group,
        "properties": properties,
    }
    console.print(json.dumps(template, indent=2))

    if conditional_props:
        console.print()
        console.print("[bold]Conditional properties (include when condition is met):[/bold]")
        for fname, (val, cond) in conditional_props.items():
            console.print(f"  {fname}: {json.dumps(val)}  [dim]when {cond}[/dim]")

    if warnings:
        console.print()
        console.print("[bold yellow]Import field overrides:[/bold yellow]")
        for w in warnings:
            console.print(w)

    if error_ports:
        console.print()
        table = Table(title="Output Ports",
                      show_header=True, header_style="bold")
        table.add_column("Port ID")
        table.add_column("Display Name")
        for p in error_ports:
            table.add_row(p["id"], p["displayName"])
        console.print(table)


@app.command()
def connectors(
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List connectors (TTS and HTTP/Custom)."""
    c = _client(debug)
    items = []
    seen_ids = set()

    # Source 1: TTS connectors from play-message connector field
    tts_path = f"{c.v2_activities()}/play-message/inputs/connector/choices"
    tts_data, tts_err = c.get_safe(tts_path)
    if tts_data and isinstance(tts_data, dict):
        for ch in tts_data.get("choices", []):
            cid = ch.get("value", "")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                items.append({
                    "id": cid,
                    "name": ch.get("name", ""),
                    "type": "TTS",
                })

    # Source 2: HTTP/Custom connectors from http-request connectorId field
    http_path = f"{c.v2_activities()}/http-request/inputs/connectorId/choices"
    http_data, http_err = c.get_safe(http_path)
    if http_data and isinstance(http_data, dict):
        for ch in http_data.get("choices", []):
            cid = ch.get("value", "")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                items.append({
                    "id": cid,
                    "name": ch.get("name", ""),
                    "type": "HTTP",
                })

    if not items:
        typer.echo("No connectors found.", err=True)
        raise typer.Exit(1)

    cols = [("ID", "id"), ("Name", "name"), ("Type", "type")]
    if output == "json":
        print_json(items)
    else:
        print_table(items, cols)


@app.command()
def events(
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List event specifications (event handlers available for flows)."""
    c = _client(debug)
    event_specs = []

    # Try to get events from the start activity definition
    act = _find_activity_safe(c, "start")
    if act:
        # Check inputGroups for eventConfig.eventsGenerated
        for ig in act.get("inputGroups", []):
            for inp in ig.get("inputs", []):
                evt_cfg = inp.get("eventConfig", {})
                if evt_cfg.get("eventsGenerated"):
                    for ev in evt_cfg["eventsGenerated"]:
                        event_specs.append(ev)
        # Also check shapeProperties.eventConfig
        shape_evt = (act.get("shapeProperties", {})
                        .get("eventConfig", {}))
        if shape_evt.get("eventsGenerated"):
            seen = {e.get("eventSpecificationName")
                    for e in event_specs}
            for ev in shape_evt["eventsGenerated"]:
                if ev.get("eventSpecificationName") not in seen:
                    event_specs.append(ev)

    # Fallback: call the eventSpecifications endpoint. Not routed on
    # produs1 (absent from the live /v3/api-docs) — kept for other
    # deployments; get_safe swallows the 404/500.
    if not event_specs:
        path = (f"/{c.org_id}/project/{c.project_id}"
                f"/v2/eventSpecifications")
        data, err = c.get_safe(path)
        if data is not None:
            if isinstance(data, list):
                event_specs = data
            elif isinstance(data, dict):
                event_specs = (data.get("eventSpecifications")
                               or data.get("items")
                               or [data])

    if not event_specs:
        typer.echo(
            "No event specifications found: the prod Flow Store API "
            "exposes no event-spec catalog endpoint. Get event names "
            "from an exported flow's eventFlows ('wxcc-flow export') "
            "or the flow-designer-flowir.md reference.",
            err=True)
        raise typer.Exit(1)

    if output == "json":
        print_json(event_specs)
        return

    cols = [
        ("Event Specification", "eventSpecificationName"),
        ("Classification", "eventClassificationName"),
        ("Source", "eventSourceName"),
    ]
    print_table(event_specs, cols, limit=0)


@app.command()
def template(
    name: str = typer.Argument("simple-inbound", help="Template name"),
    out: str = typer.Option(None, "-o", "--out", help="Output file path"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get a starter FlowIR template."""
    templates = {
        "simple-inbound": {
            "name": "New_Flow",
            "flowType": "FLOW",
            "description": "",
            "variables": [],
            "nodes": [
                {
                    "id": "node-start",
                    "name": "StartFlow",
                    "activityType": "start",
                    "properties": {
                        "activityName": "start",
                        "flowType": {
                            "eventSourceName": "WebexContactCenter",
                            "eventClassificationName": "VoiceInteractions",
                            "eventSpecificationName": "ContactStartWorkflow",
                        },
                    },
                },
                {
                    "id": "node-end",
                    "name": "DisconnectContact",
                    "activityType": "end",
                    "properties": {"activityName": "disconnect-contact"},
                },
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "from": "StartFlow",
                    "to": "DisconnectContact",
                    "condition": "out",
                    "properties": {},
                }
            ],
            "eventFlows": {},
        }
    }
    tpl = templates.get(name)
    if not tpl:
        typer.echo(f"Unknown template '{name}'. Available: {', '.join(templates.keys())}", err=True)
        raise typer.Exit(1)
    if out:
        _write_json(tpl, out)
    else:
        print_json(tpl)


# ── Spec drift (Phase D): live /v3/api-docs vs the committed snapshot ─
_HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _spec_ops(spec: dict) -> dict:
    """Flatten a spec to {(METHOD, path): operation-dict}."""
    ops = {}
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for m in _HTTP_METHODS:
            op = item.get(m)
            if isinstance(op, dict):
                ops[(m.upper(), path)] = op
    return ops


def _diff_specs(snap: dict, live: dict):
    """Return (added, removed, changed) op keys, live vs snapshot."""
    old, new = _spec_ops(snap), _spec_ops(live)
    added = sorted(k for k in new if k not in old)
    removed = sorted(k for k in old if k not in new)
    changed = sorted(
        k for k in new
        if k in old and json.dumps(new[k], sort_keys=True) != json.dumps(old[k], sort_keys=True)
    )
    return added, removed, changed


@app.command("spec-diff")
def spec_diff(
    snapshot: str = typer.Option(
        "specs/flow-store-api-docs.json", "--snapshot",
        help="Committed spec snapshot to diff against (default is relative to "
             "the toolkit repo root — run from there, or pass an absolute path)"),
    exit_code: bool = typer.Option(
        False, "--exit-code",
        help="Exit 1 when the live contract differs from the snapshot (CI use)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Diff the LIVE Flow Store contract (GET /v3/api-docs) against the committed snapshot."""
    snap_path = Path(snapshot)
    if not snap_path.exists():
        typer.echo(f"Error: File not found: {snapshot}", err=True)
        raise typer.Exit(1)
    snap = json.loads(snap_path.read_text())
    live = _client(debug).get("/v3/api-docs")
    if not isinstance(live, dict):
        typer.echo("Error: live /v3/api-docs did not return a JSON object.", err=True)
        raise typer.Exit(1)

    added, removed, changed = _diff_specs(snap, live)
    old_ops, new_ops = _spec_ops(snap), _spec_ops(live)
    for m, p in added:
        typer.echo(f"+ {m} {p}  ({new_ops[(m, p)].get('operationId', '?')})")
    for m, p in removed:
        typer.echo(f"- {m} {p}  ({old_ops[(m, p)].get('operationId', '?')})")
    for m, p in changed:
        typer.echo(f"~ {m} {p}  ({new_ops[(m, p)].get('operationId', '?')})")
    typer.echo(
        f"Live {len(new_ops)} ops / snapshot {len(old_ops)} ops — "
        f"{len(added)} added, {len(removed)} removed, {len(changed)} changed."
    )
    if not (added or removed or changed):
        typer.echo("In sync.")
    elif exit_code:
        raise typer.Exit(1)


# ── Init (materialize the bundled Claude Code playbook) ──────────────
from wxcc_flow.init_playbook import init as init_command  # noqa: E402
app.command(name="init")(init_command)

# ── Generated `api <group> <op>` namespace (tools/generator) ─────────
from wxcc_flow import generated  # noqa: E402
generated.register(app)  # mounts `wxcc-flow api <group> <op>`


def run():
    app()
