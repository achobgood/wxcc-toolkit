"""Platform-level commands — templates, consume, UI import/export, projects,
connectors, resource collections, user preferences.

Template catalog is org-independent (Cisco-curated on prod). The v1
:export/:import pair transports the full FlowVersion object (including UI
diagram data) — the CLI never generates that shape, only round-trips it.
"""
import json

import typer

from wxcc_flow.client import FlowClient
from wxcc_flow.output import print_json, print_table

TEMPLATE_COLUMNS = [
    ("ID", "id"),
    ("Name", "name"),
    ("Type", "flowType"),
    ("Description", "description"),
]


def templates(
    name: str = typer.Option(None, "--name", help="Filter by template name"),
    flow_type: str = typer.Option(None, "--type", help="FLOW or SUBFLOW"),
    page: int = typer.Option(0, "--page"),
    size: int = typer.Option(50, "--size"),
    show_inactive: bool = typer.Option(False, "--show-inactive", help="Include deleted templates"),
    get_all: bool = typer.Option(False, "--all", help="Ignore feature flags"),
    output: str = typer.Option("table", "-o", "--output", help="Output format: table|json"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List the flow/subflow template catalog."""
    c = FlowClient(debug=debug)
    params = {"page": page, "size": size}
    if name:
        params["name"] = name
    if flow_type:
        params["flowType"] = flow_type
    if show_inactive:
        params["showInactive"] = "true"
    if get_all:
        params["getAll"] = "true"
    data = c.get("/templates", params=params)
    items = data if isinstance(data, list) else data.get("templates", data.get("items", []))
    if output == "json":
        print_json(data)
    else:
        print_table(items, TEMPLATE_COLUMNS, limit=0)


def template_get(
    template_id: str = typer.Argument(..., help="Template ID (see 'wxcc-flow templates')"),
    out: str = typer.Option(None, "--out", help="Output file path (default: stdout)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get one flow/subflow template by ID."""
    c = FlowClient(debug=debug)
    data = c.get(f"/templates/{template_id}")
    if out:
        from wxcc_flow.main import _write_json
        _write_json(data, out)
    else:
        print_json(data)


def consume_template(
    template_name: str = typer.Argument(..., help="Template name (see 'wxcc-flow templates')"),
    flow_name: str = typer.Argument(..., help="Name for the new flow"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing flow with the same name"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Create a new flow from a catalog template."""
    c = FlowClient(debug=debug)
    params = {"templateName": template_name, "flowName": flow_name,
              "flowType": flow_type, "overwrite": str(overwrite).lower()}
    data = c.post(f"{c.v1_flows()}:consume-template", params=params)
    flow = data.get("flow", data) if isinstance(data, dict) else data
    typer.echo(f"Created flow '{flow_name}' from template '{template_name}'"
               f"  id={flow.get('id', 'unknown') if isinstance(flow, dict) else 'unknown'}")
    print_json(data)


def consume(
    file: str = typer.Argument(..., help="Path to a flow JSON file (UI-export shape)"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing flow with the same name"),
    template_name: str = typer.Option(None, "--template-name", help="Template name to associate"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Create a new flow from a JSON string (UI-export shape, transported verbatim)."""
    from wxcc_flow.main import _read_flowir
    c = FlowClient(debug=debug)
    flow_json = _read_flowir(file)
    params = {"flowType": flow_type, "overwrite": str(overwrite).lower()}
    if template_name:
        params["templateName"] = template_name
    # Contract: the request body is a JSON *string* containing the flow JSON.
    data = c.post(f"{c.v1_flows()}:consume", json_body=json.dumps(flow_json),
                  params=params)
    print_json(data)


def export_ui(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    version: str = typer.Option("latest", "--version", help="'latest', 'draft', or a version ID"),
    out: str = typer.Option(None, "--out", help="Output file path (default: stdout)"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Export the full v1 FlowVersion object (incl. UI diagram data)."""
    c = FlowClient(debug=debug)
    # Contract quirk: this v1 endpoint names the type param 'Flow Type'
    # (with a space), not 'flowType'.
    params = {"version": version, "Flow Type": flow_type}
    data = c.get(f"{c.v1_flow(flow_id)}:export", params=params)
    if out:
        from wxcc_flow.main import _write_json
        _write_json(data, out)
    else:
        print_json(data)


def import_ui(
    file: str = typer.Argument(..., help="Path to a UI-exported flow JSON file"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing flow with the same name"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Import a UI-exported flow JSON (v1 shape, transported verbatim)."""
    from pathlib import Path as _Path
    c = FlowClient(debug=debug)
    p = _Path(file)
    if not p.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(1)
    # Contract quirks: this is a MULTIPART endpoint (requestBody = file:
    # binary; raw JSON bodies 500), overwrite is the string yes/no (not a
    # boolean), and the type param is 'Flow Type' (with a space).
    params = {"overwrite": "yes" if overwrite else "no", "Flow Type": flow_type}
    data = c.post_multipart(f"{c.v1_flows()}:import", p.name, p.read_bytes(),
                            params=params)
    flow = data.get("flow", data) if isinstance(data, dict) else data
    typer.echo(f"Imported flow: {flow.get('name', 'unknown') if isinstance(flow, dict) else 'unknown'}"
               f"  id={flow.get('id', 'unknown') if isinstance(flow, dict) else 'unknown'}")
    print_json(data)


def projects(
    page: int = typer.Option(0, "--page"),
    size: int = typer.Option(10, "--size"),
    output: str = typer.Option("table", "-o", "--output", help="Output format: table|json"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List the org's Flow Store projects.

    NOTE: the system-provisioned default project may be missing from this
    list — the configured project ID comes from userPreferences instead
    (see 'wxcc-flow user-prefs').
    """
    c = FlowClient(debug=debug)
    data = c.get(f"/{c.org_id}/project", params={"page": page, "size": size})
    items = data if isinstance(data, list) else data.get("projects", data.get("items", []))
    if output == "json":
        print_json(data)
    else:
        cols = [("ID", "id"), ("Name", "name"), ("Default", "default"),
                ("Created By", "createdBy"), ("Created", "createdDate")]
        print_table(items, cols, limit=0)


def project(
    project_id: str = typer.Argument(None, help="Project ID (default: the configured project)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get one project by ID (defaults to the configured project)."""
    c = FlowClient(debug=debug)
    pid = project_id or c.project_id
    data = c.get(f"/{c.org_id}/project/{pid}")
    print_json(data)


def connector_list(
    output: str = typer.Option("table", "-o", "--output", help="Output format: table|json"),
    project_id: str = typer.Option(None, "--project-id",
        help="Project to query. NOTE: the connector-controller 404s on the "
             "system-provisioned project — pass a user-created project ID "
             "(see 'wxcc-flow projects')"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List raw connector entities (connector-controller; 'connectors' shows
    the choices-based view used by activities)."""
    c = FlowClient(debug=debug)
    pid = project_id or c.project_id
    data = c.get(f"/{c.org_id}/project/{pid}/connector")
    items = data if isinstance(data, list) else data.get("connectors", data.get("items", []))
    if output == "json":
        print_json(data)
    else:
        cols = [("ID", "id"), ("Name", "name"), ("Type", "type")]
        print_table(items, cols, limit=0)


def connector(
    connector_id: str = typer.Argument(..., help="Connector ID"),
    project_id: str = typer.Option(None, "--project-id",
        help="Project to query (connector-controller 404s on the "
             "system-provisioned project — pass a user-created project ID)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get one connector entity by ID."""
    c = FlowClient(debug=debug)
    pid = project_id or c.project_id
    data = c.get(f"/{c.org_id}/project/{pid}/connector/{connector_id}")
    print_json(data)


def resource_collections(
    page: int = typer.Option(0, "--page"),
    size: int = typer.Option(10, "--size"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List resource collections visible to the current user."""
    c = FlowClient(debug=debug)
    data = c.get(f"/{c.org_id}/resource-collections",
                 params={"page": page, "size": size})
    print_json(data)


def user_prefs(
    debug: bool = typer.Option(False, "--debug"),
):
    """Show the current user's Flow Designer preferences (incl. the real
    project ID used for auto-resolution)."""
    c = FlowClient(debug=debug)
    data = c.get(f"/{c.org_id}/userPreferences")
    print_json(data)


def register(app: typer.Typer) -> None:
    app.command()(templates)
    app.command("template-get")(template_get)
    app.command("consume-template")(consume_template)
    app.command()(consume)
    app.command("export-ui")(export_ui)
    app.command("import-ui")(import_ui)
    app.command()(projects)
    app.command()(project)
    app.command("connector-list")(connector_list)
    app.command()(connector)
    app.command("resource-collections")(resource_collections)
    app.command("user-prefs")(user_prefs)
