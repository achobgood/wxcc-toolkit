"""Platform-level commands — templates, consume, UI import/export, projects,
connectors, resource collections, user preferences.

Template catalog is org-independent (Cisco-curated on prod). The v1
:export/:import pair transports the full FlowVersion object (including UI
diagram data) — the CLI never generates that shape, only round-trips it.
"""
import json

import typer

from wxcc_flow.client import FlowClient
from wxcc_flow.output import print_json

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


def register(app: typer.Typer) -> None:
    app.command("template-get")(template_get)
    app.command("consume-template")(consume_template)
    app.command()(consume)
    app.command("export-ui")(export_ui)
    app.command("import-ui")(import_ui)
