"""wxcc-flow — CLI for Cisco WxCC Flow Designer REST APIs."""
import json
import sys
from pathlib import Path
from typing import Optional

import typer

from wxcc_flow import __version__
from wxcc_flow.client import FlowClient, FlowStoreError
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


def _read_flowir(file_path: str) -> dict:
    p = Path(file_path)
    if not p.exists():
        typer.echo(f"Error: File not found: {file_path}", err=True)
        raise typer.Exit(1)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


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
):
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


@app.command()
def whoami(debug: bool = typer.Option(False, "--debug")):
    """Show current user and org info."""
    c = _client(debug)
    user = c.get("/auth/user")
    typer.echo(f"User:    {user}" if isinstance(user, str) else f"User:    {json.dumps(user)}")
    typer.echo(f"Org:     {c._org_id or '(not configured)'}")
    typer.echo(f"Project: {c._project_id or '(not configured)'}")

    health = c.get_text("/health")
    typer.echo(f"Health:  {health.strip()}")


# ── Flow Management ──────────────────────────────────────────────────

FLOW_COLUMNS = [
    ("ID", "id"),
    ("Name", "name"),
    ("Status", "status"),
    ("Type", "flowType"),
    ("Updated", "lastUpdated.date"),
]


@app.command("list")
def list_flows(
    output: str = typer.Option("table", "-o", "--output", help="Output format: table|json"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List all flows."""
    c = _client(debug)
    data = c.get(c.v1_flows())
    flows = data if isinstance(data, list) else data.get("flows", data.get("items", [data]))

    if output == "json":
        print_json(flows)
    else:
        print_table(flows, FLOW_COLUMNS)


@app.command()
def get(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    output: str = typer.Option("json", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get flow metadata."""
    c = _client(debug)
    data = c.get(c.v1_flow(flow_id))
    print_json(data)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Full-text search across flows."""
    c = _client(debug)
    data = c.get(f"{c.v1_flows()}:search", params={"query": query})
    flows = data if isinstance(data, list) else data.get("data", data.get("flows", data.get("items", [])))
    if output == "json":
        print_json(flows)
    else:
        print_table(flows, FLOW_COLUMNS)


@app.command()
def create(
    file: str = typer.Argument(..., help="Path to FlowIR JSON file"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Import/create a flow from a FlowIR JSON file."""
    c = _client(debug)
    flowir = _read_flowir(file)
    data = c.post(f"{c.v2_flows()}:import", json_body=flowir)
    typer.echo(f"Created flow: {data.get('id', data.get('name', 'unknown'))}")
    print_json(data)


@app.command("save-draft")
def save_draft(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    file: str = typer.Argument(..., help="Path to FlowIR JSON file"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Save a FlowIR file as draft for an existing flow."""
    c = _client(debug)
    flowir = _read_flowir(file)
    data = c.post(f"{c.v2_flow(flow_id)}/draft", json_body=flowir)
    typer.echo(f"Draft saved for flow {flow_id}")
    if data:
        print_json(data)


@app.command()
def export(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    out: str = typer.Option(None, "-o", "--out", help="Output file path (default: stdout)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Export a flow as FlowIR JSON (v2 format)."""
    c = _client(debug)
    data = c.get(f"{c.v2_flow(flow_id)}:export")
    if out:
        _write_json(data, out)
    else:
        print_json(data)


@app.command()
def draft(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    out: str = typer.Option(None, "-o", "--out", help="Output file path"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get the current draft of a flow as FlowIR."""
    c = _client(debug)
    data = c.get(f"{c.v2_flow(flow_id)}/draft")
    if out:
        _write_json(data, out)
    else:
        print_json(data)


@app.command()
def validate(
    file: str = typer.Argument(None, help="Path to FlowIR JSON file"),
    flow_id: str = typer.Option(None, "--id", help="Validate a persisted flow by ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Dry-run validate a FlowIR file or persisted flow."""
    c = _client(debug)
    if flow_id:
        data = c.get(f"{c.v2_flow(flow_id)}/draft")
        result = c.post(f"{c.v2_flows()}:validate", json_body=data)
    elif file:
        flowir = _read_flowir(file)
        result = c.post(f"{c.v2_flows()}:validate", json_body=flowir)
    else:
        typer.echo("Error: Provide a FILE path or --id FLOW_ID.", err=True)
        raise typer.Exit(1)

    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    if not errors and not warnings:
        typer.echo("Validation passed.")
    else:
        if errors:
            typer.echo(f"Errors ({len(errors)}):")
            for e in errors:
                typer.echo(f"  - {e}")
        if warnings:
            typer.echo(f"Warnings ({len(warnings)}):")
            for w in warnings:
                typer.echo(f"  - {w}")
    print_json(result)


@app.command()
def publish(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Publish a flow draft."""
    c = _client(debug)
    data = c.post(f"{c.v1_flow(flow_id)}:publish", json_body={}, params={"skipValidation": "true"})
    typer.echo(f"Published flow {flow_id}")
    if data:
        print_json(data)


@app.command()
def lock(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Lock a flow for editing."""
    c = _client(debug)
    c.post(f"{c.v1_flow(flow_id)}:lock")
    typer.echo(f"Locked flow {flow_id}")


@app.command()
def unlock(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Unlock a flow."""
    c = _client(debug)
    c.post(f"{c.v1_flow(flow_id)}:unlock")
    typer.echo(f"Unlocked flow {flow_id}")


@app.command()
def copy(
    flow_id: str = typer.Argument(..., help="Flow ID to copy"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Copy an existing flow."""
    c = _client(debug)
    data = c.post(f"{c.v1_flows()}:copy", json_body={}, params={"sourceFlowId": flow_id})
    typer.echo(f"Copied flow {flow_id}")
    print_json(data)


@app.command()
def delete(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Delete a flow."""
    c = _client(debug)
    c.delete(c.v1_flow(flow_id))
    typer.echo(f"Deleted flow {flow_id}")


@app.command()
def versions(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List published versions of a flow."""
    c = _client(debug)
    data = c.get(f"{c.v1_flow(flow_id)}/versions")
    vlist = data if isinstance(data, list) else data.get("versions", data.get("items", []))
    cols = [("Version ID", "id"), ("Label", "label"), ("Published", "publishedDate")]
    if output == "json":
        print_json(vlist)
    else:
        print_table(vlist, cols)


def _find_activity_safe(client: FlowClient, name: str):
    """Find an activity by name, returning None if not found."""
    data = client.get(client.v2_activities())
    if isinstance(data, dict):
        for _cat, activity_list in data.items():
            if isinstance(activity_list, list):
                for act in activity_list:
                    if act.get("name") == name:
                        return act
    return None


# ── Activity Registry ────────────────────────────────────────────────

@app.command()
def activities(
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List all available activities."""
    c = _client(debug)
    data = c.get(c.v2_activities())
    # Response is a dict keyed by category (logic, action, etc.), each containing a list
    items = []
    if isinstance(data, dict):
        for category, activity_list in data.items():
            if isinstance(activity_list, list):
                for act in activity_list:
                    act["category"] = category
                    items.append(act)
    elif isinstance(data, list):
        items = data
    cols = [("ID", "id"), ("Display Name", "displayName"), ("Name", "name"), ("Category", "category")]
    if output == "json":
        print_json(items)
    else:
        print_table(items, cols)


@app.command()
def describe(
    activity: str = typer.Argument(..., help="Activity name (e.g. play-message)"),
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Describe an activity — properties, inputs, outputs."""
    c = _client(debug)
    act = c.get_activity_definition(activity)

    if output == "json":
        print_json(act)
        return

    _print_activity_summary(act)


_SKIP_GROUPS = {"Decryption settings"}
_describe_console = Console()


def _print_activity_summary(act: dict) -> None:
    """Print a formatted summary of an activity definition."""
    name = act.get("name", "")
    display = act.get("displayName", "")
    desc = act.get("description", "")
    category = act.get("category", "")

    _describe_console.print(f"[bold]Activity:[/bold] {name} ({display})")
    if desc:
        _describe_console.print(f"[bold]Description:[/bold] {desc}")
    if category:
        _describe_console.print(f"[bold]Group:[/bold] {category}")
    _describe_console.print()

    # --- Input Fields ---
    _print_input_fields(act)

    # --- Output Variables ---
    _print_output_variables(act)

    # --- Output Ports ---
    _print_output_ports(act)


def _print_input_fields(act: dict) -> None:
    """Print input fields from inputGroups, deduplicated by composite key.

    Fields with the same name but different flagName/flagValue are
    feature-flag variants (e.g. set-announcement's attributeTag has
    an "Attribute tag" variant and a "Greeting Purpose" variant).
    We show each variant separately with its flag annotation.
    """
    groups = act.get("inputGroups", [])

    # --- Pass 1: collect all inputs to detect multi-variant fields ---
    all_inputs = []  # (inp_dict, group_name)
    name_count = {}  # field_name -> number of distinct flag variants
    seen_keys = set()
    for group in groups:
        group_name = group.get("name", "")
        if group_name in _SKIP_GROUPS:
            continue
        for inp in group.get("inputs", []):
            field_name = inp.get("name", "")
            flag_name = inp.get("flagName") or ""
            flag_value = inp.get("flagValue") or ""
            dedup_key = (field_name, flag_name, flag_value)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            all_inputs.append(inp)
            name_count[field_name] = name_count.get(field_name, 0) + 1

    # --- Pass 2: build display rows ---
    rows = []
    for inp in all_inputs:
        field_name = inp.get("name", "")
        flag_name = inp.get("flagName") or ""
        flag_value = inp.get("flagValue") or ""
        condition = ""
        show_on = inp.get("showOnCondition")
        if isinstance(show_on, dict):
            cond_name = show_on.get("name", "")
            cond_val = show_on.get("value", "")
            if cond_name:
                condition = f"{cond_name} == {cond_val}"
        elif isinstance(show_on, str) and show_on:
            condition = show_on
        # Only annotate display name and flag info for multi-variant
        # fields (same name, different flagName/flagValue)
        display_name = field_name
        is_multi_variant = name_count.get(field_name, 1) > 1
        if is_multi_variant:
            props_text = (inp.get("properties") or {}).get("text", "")
            if props_text:
                display_name = f"{field_name} [{props_text}]"
            if flag_name:
                flag_note = f"flag:{flag_name}={flag_value}"
                condition = (f"{condition}; {flag_note}"
                             if condition else flag_note)
        rows.append({
            "name": display_name,
            "type": inp.get("type", ""),
            "required": "Yes" if inp.get("required") else "No",
            "component": inp.get("component", ""),
            "default": str(inp.get("defaultValue", "--"))
                if inp.get("defaultValue") is not None else "--",
            "condition": condition,
        })

    if rows:
        table = Table(title="Input Fields", show_header=True,
                      header_style="bold")
        for col in ["Field", "Type", "Required", "Component",
                     "Default", "Condition"]:
            table.add_column(col)
        for r in rows:
            table.add_row(r["name"], r["type"], r["required"],
                          r["component"], r["default"], r["condition"])
        _describe_console.print(table)
        _describe_console.print()


def _print_output_variables(act: dict) -> None:
    """Print output variables."""
    outputs = act.get("outputs", [])
    if not outputs:
        return
    table = Table(title="Output Variables", show_header=True,
                  header_style="bold")
    for col in ["Name", "Type", "Description"]:
        table.add_column(col)
    for o in outputs:
        table.add_row(
            o.get("name", ""),
            o.get("type", ""),
            o.get("description", ""),
        )
    _describe_console.print(table)
    _describe_console.print()


def _print_output_ports(act: dict) -> None:
    """Print output ports from errorPathLinks and outputConditions."""
    ports = {}
    # errorPathLinks
    for link in act.get("shapeProperties", {}).get("errorPathLinks", []):
        pid = link.get("id", "")
        ports[pid] = {
            "condition": pid,
            "label": link.get("displayName", ""),
            "is_error": "Yes",
        }
    # outputConditions (non-error ports)
    for cond in act.get("outputConditions", []):
        cid = cond.get("id", "")
        if cid not in ports:
            ports[cid] = {
                "condition": cid,
                "label": cond.get("displayName", ""),
                "is_error": "No",
            }
    if not ports:
        return
    table = Table(title="Output Ports", show_header=True,
                  header_style="bold")
    for col in ["Condition", "Label", "Is Error"]:
        table.add_column(col)
    for p in ports.values():
        table.add_row(p["condition"], p["label"], p["is_error"])
    _describe_console.print(table)


@app.command()
def schema(
    activity: str = typer.Argument(..., help="Activity name"),
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Build a FlowIR node template from the activity definition.

    Uses REAL property names from inputGroups (not the broken
    /schema endpoint which returns wrong propertyHints names).
    """
    c = _client(debug)
    act = c.get_activity_definition(activity)

    if output == "json":
        print_json(act)
        return

    # Determine activityType from group
    raw_group = act.get("group", "action")
    group = raw_group.get("name", str(raw_group)) if isinstance(raw_group, dict) else str(raw_group)
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
    for ig in act.get("inputGroups", []):
        gname = ig.get("name", "")
        if gname == "Decryption settings":
            continue
        for inp in ig.get("inputs", []):
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
            if default is not None:
                if isinstance(default, str) and default.startswith('"') and default.endswith('"'):
                    default = default[1:-1]
                val = default
            else:
                val = f"<{inp.get('type', 'string')}>"
            show_cond = inp.get("showOnCondition")
            if show_cond:
                cond_str = f"{show_cond.get('name', '')} == {show_cond.get('value', '')}" if isinstance(show_cond, dict) else str(show_cond)
                conditional_props[field_name] = (val, cond_str)
            else:
                properties[field_name] = val

    # Build output ports from errorPathLinks
    error_ports = []
    for link in act.get("shapeProperties", {}).get("errorPathLinks", []):
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
        table = Table(title="Output Ports (errorPathLinks)",
                      show_header=True, header_style="bold")
        table.add_column("Port ID")
        table.add_column("Display Name")
        for p in error_ports:
            table.add_row(p["id"], p["displayName"])
        console.print(table)


@app.command()
def choices(
    activity: str = typer.Argument(..., help="Activity name"),
    input_name: str = typer.Argument(..., help="Input/property name"),
    search_query: str = typer.Option(None, "--search", help="Filter choices"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get dropdown values for an activity input."""
    c = _client(debug)
    params = {}
    if search_query:
        params["query"] = search_query
    path = f"{c.v2_activities()}/{activity}/inputs/{input_name}/choices"
    try:
        data = c.get(path, params=params)
        print_json(data)
    except FlowStoreError as e:
        if e.status_code != 400:
            typer.echo(f"Error: HTTP {e.status_code}: {e.body[:200]}", err=True)
            raise typer.Exit(1)
        # Check if this is a RadioGroup or RadioGroupWithValue input
        body = e.body
        is_radio = ("RadioGroup" in body
                     or "RadioGroupWithValue" in body)
        if not is_radio:
            typer.echo(f"Error: HTTP 400: {body[:200]}", err=True)
            raise typer.Exit(1)

        # Fetch the full activity definition and find the input
        act = c.get_activity_definition(activity)
        matched_input = None
        for ig in act.get("inputGroups", []):
            for inp in ig.get("inputs", []):
                if inp.get("name") == input_name:
                    matched_input = inp
                    break
            if matched_input:
                break

        if not matched_input:
            typer.echo(
                f"Error: Input '{input_name}' not found in "
                f"'{activity}' definition.", err=True)
            raise typer.Exit(1)

        component = matched_input.get("component", "")
        console = Console()
        console.print(
            f"[bold]{input_name}[/bold] is a [yellow]{component}"
            f"[/yellow] — the /choices endpoint does not support "
            f"this type.")
        console.print()

        # Show static options from the input definition
        options = (matched_input.get("choices")
                   or matched_input.get("options")
                   or matched_input.get("values")
                   or [])
        if options:
            table = Table(title=f"Static options for {input_name}",
                          show_header=True, header_style="bold")
            if options and isinstance(options[0], dict):
                table.add_column("Value")
                table.add_column("Label")
                for opt in options:
                    val = str(opt.get("value", opt.get("id", "")))
                    label = opt.get("label",
                                    opt.get("displayName", ""))
                    table.add_row(val, label)
            else:
                table.add_column("Value")
                for opt in options:
                    table.add_row(str(opt))
            console.print(table)
        else:
            # For RadioGroupWithValue, explain the pattern
            if "WithValue" in component:
                console.print(
                    "RadioGroupWithValue inputs accept a typed "
                    "value plus a radioName suffix field.\n"
                    "Check the activity definition "
                    "('wxcc-flow describe " + activity + "') "
                    "for the full input structure.")
            else:
                console.print(
                    "No static options found in the definition. "
                    "Run 'wxcc-flow describe " + activity + "' "
                    "to inspect the input.")


# ── Org / Config ─────────────────────────────────────────────────────

@app.command("global-vars")
def global_vars(
    output: str = typer.Option("table", "-o", "--output"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List org-level global variables."""
    c = _client(debug)
    data = c.get(f"{c.v1_flows()}/global-variables")
    items = data if isinstance(data, list) else data.get("variables", data.get("globalVariables", data.get("items", [])))
    cols = [("Name", "name"), ("Type", "type"), ("Value", "value")]
    if output == "json":
        print_json(items)
    else:
        print_table(items, cols)


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

    # Fallback: call the eventSpecifications endpoint
    if not event_specs:
        path = (f"/v2/{c.org_id}/project/{c.project_id}"
                f"/eventSpecifications")
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
            "No event specifications found. The start activity "
            "may not expose events in this org's activity registry.",
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


@app.command("test-expr")
def test_expr(
    expression: str = typer.Argument(..., help="Flow expression to test"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Test a Pebble/flow expression."""
    c = _client(debug)
    data = c.post("/expressionTest", json_body={"expression": expression})
    print_json(data)


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
                    "from": "node-start",
                    "to": "node-end",
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


@app.command()
def health(debug: bool = typer.Option(False, "--debug")):
    """Check Flow Store API health."""
    c = _client(debug)
    h = c.get_text("/health")
    typer.echo(h.strip())
    info = c.get("/build_info")
    print_json(info)


# ── Init (materialize the bundled Claude Code playbook) ──────────────
from wxcc_flow.init_playbook import init as init_command  # noqa: E402
app.command(name="init")(init_command)


def run():
    app()
