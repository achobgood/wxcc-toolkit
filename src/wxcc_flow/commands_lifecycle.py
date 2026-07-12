"""Flow lifecycle & metadata commands — patch, revert, versions, tags, prefs.

Covers draft patching (FDL 2.0 PATCH), version pinning/revert, name checks,
flow metadata (merge-patch rename), tags, tag history, flow preferences, and
where-used lookups (flows:check).
"""
import json
import sys

import typer

from wxcc_flow.client import FlowClient
from wxcc_flow.output import print_json, print_table


def _read_json_or_stdin(file_path: str) -> dict:
    """Read a JSON body from a file path, or stdin when the path is '-'."""
    if file_path == "-":
        return json.load(sys.stdin)
    from wxcc_flow.main import _read_flowir
    return _read_flowir(file_path)


def patch(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    file: str = typer.Argument(..., help="Path to patch JSON ('-' for stdin). "
                               "Keys: upsert_nodes/upsert_edges/remove_node_names/"
                               "remove_edge_keys, or top-level FlowV2 fields."),
    expected_version: int = typer.Option(None, "--expected-version",
        help="Optimistic-lock version; auto-resolved from the current draft if omitted"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Patch a flow draft in place (partial update, FDL 2.0)."""
    c = FlowClient(debug=debug)
    body = _read_json_or_stdin(file)
    if expected_version is None:
        current = c.get(c.v2_flow(flow_id), params={"flowType": flow_type})
        cur = current.get("flow", current) if isinstance(current, dict) else current
        expected_version = cur.get("version", 0) or 0
    data = c.patch(c.v2_flow(flow_id), json_body=body,
                   params={"expectedVersion": expected_version, "flowType": flow_type})
    typer.echo(f"Patched draft of flow {flow_id} (expectedVersion={expected_version})")
    if data:
        print_json(data)


def revert(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    version_id: str = typer.Argument(..., help="Version ID to revert to (see 'wxcc-flow versions')"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Revert a flow to a previous published version."""
    c = FlowClient(debug=debug)
    data = c.post(f"{c.v1_flow(flow_id)}:revert",
                  params={"versionId": version_id, "flowType": flow_type})
    typer.echo(f"Reverted flow {flow_id} to version {version_id}")
    if data:
        print_json(data)


def unique_name(
    name: str = typer.Argument(..., help="Flow name to check"),
    flow_id: str = typer.Option(None, "--flow-id", help="Exclude this flow ID (for renames)"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Check whether a flow name is unique. Exits 1 if the name is taken."""
    c = FlowClient(debug=debug)
    params = {"flowName": name, "flowType": flow_type}
    if flow_id:
        params["flowId"] = flow_id
    from wxcc_flow.client import FlowStoreError
    try:
        data = c.post(f"{c.v1_flows()}:unique-name", params=params)
    except FlowStoreError as e:
        # Server signals a taken name with a 400.
        typer.echo(f"Name '{name}' is NOT unique: {e.body[:200]}", err=True)
        raise typer.Exit(1)
    result = data if data else {}
    unique = result.get("unique", result.get("isUnique")) if isinstance(result, dict) else None
    if unique is False:
        typer.echo(f"Name '{name}' is NOT unique.")
        raise typer.Exit(1)
    typer.echo(f"Name '{name}' is unique.")
    if result:
        print_json(result)


def version(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    ref: str = typer.Argument("latest", help="'latest', 'draft', or a version ID"),
    out: str = typer.Option(None, "--out", help="Output file path (default: stdout)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get one flow version object: latest published, current draft, or by ID."""
    c = FlowClient(debug=debug)
    # 'latest' and 'draft' are dedicated sub-resources; anything else is a
    # version ObjectId — all three share the same path shape.
    data = c.get(f"{c.v1_flow(flow_id)}/versions/{ref}")
    if out:
        from wxcc_flow.main import _write_json
        _write_json(data, out)
    else:
        print_json(data)


def update(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    name: str = typer.Option(None, "--name", help="New flow name"),
    description: str = typer.Option(None, "--description", help="New flow description"),
    flow_type: str = typer.Option("FLOW", "--type", help="FLOW or SUBFLOW"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Rename / re-describe a flow (applies to the draft; publish to propagate).

    Uses the v2 draft PATCH — the v1 merge-patch endpoint returns 200 but
    silently ignores name/description changes (verified live 2026-07-11).
    The new name shows at flow level (list/get) after the next publish.
    """
    body = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if not body:
        typer.echo("Error: Provide --name and/or --description.", err=True)
        raise typer.Exit(1)
    c = FlowClient(debug=debug)
    current = c.get(c.v2_flow(flow_id), params={"flowType": flow_type})
    cur = current.get("flow", current) if isinstance(current, dict) else current
    expected_version = cur.get("version", 0) or 0
    data = c.patch(c.v2_flow(flow_id), json_body=body,
                   params={"expectedVersion": expected_version,
                           "flowType": flow_type})
    typer.echo(f"Updated draft of flow {flow_id}: {', '.join(body.keys())} "
               f"(publish to propagate to the flow level)")
    if data:
        print_json(data)


def tags(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    all_tags: bool = typer.Option(False, "--all", help="Return all eligible tags, not just attached ones"),
    tag_id: str = typer.Option(None, "--tag-id", help="One of 'Live', 'Latest', 'Test', 'Dev' (must be in use)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List the version tags of a flow (Live/Latest/Test/Dev)."""
    c = FlowClient(debug=debug)
    params = {}
    if all_tags:
        params["all"] = "true"
    if tag_id:
        params["tagId"] = tag_id
    data = c.get(f"{c.v1_flow(flow_id)}/tags", params=params or None)
    print_json(data)


def tag_history(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Show which flow versions each tag has pointed to over time."""
    c = FlowClient(debug=debug)
    data = c.get(f"{c.v1_flow(flow_id)}/tagHistories")
    print_json(data)


def prefs(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List a flow's preferences (autoSave, viewSettings, ...)."""
    c = FlowClient(debug=debug)
    data = c.get(f"{c.v1_flow(flow_id)}/preferences")
    print_json(data)


def prefs_set(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    file: str = typer.Argument(..., help="Path to a JSON array of {name,value,type} preferences ('-' for stdin)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Replace flow preferences (PUT) from a JSON file."""
    c = FlowClient(debug=debug)
    body = _read_json_or_stdin(file)
    data = c.put(f"{c.v1_flow(flow_id)}/preferences", json_body=body)
    typer.echo(f"Preferences updated for flow {flow_id}")
    if data:
        print_json(data)


def prefs_add(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    file: str = typer.Argument(..., help="Path to a JSON array of {name,value,type} preferences ('-' for stdin)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Add flow preferences (POST) from a JSON file."""
    c = FlowClient(debug=debug)
    body = _read_json_or_stdin(file)
    data = c.post(f"{c.v1_flow(flow_id)}/preferences", json_body=body)
    typer.echo(f"Preferences added for flow {flow_id}")
    if data:
        print_json(data)


def prefs_rm(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    names: list[str] = typer.Argument(..., help="Preference names to remove"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Remove flow preferences by name."""
    c = FlowClient(debug=debug)
    data = c.delete_with_body(f"{c.v1_flow(flow_id)}/preferences", json_body=list(names))
    typer.echo(f"Removed preferences from flow {flow_id}: {', '.join(names)}")
    if data:
        print_json(data)


def check(
    global_var: str = typer.Option(None, "--global-var", help="Find flows using this global variable"),
    ep_id: str = typer.Option(None, "--ep-id", help="Find flows attached to this entry point ID"),
    skill_id: str = typer.Option(None, "--skill-id", help="Find flows using this skill ID"),
    business_hour: str = typer.Option(None, "--business-hour", help="Find flows using this business-hours entity"),
    search: str = typer.Option(None, "--search", help="Search term"),
    flow_id: str = typer.Option(None, "--flow-id", help="Restrict to one flow ID"),
    view: str = typer.Option("basic", "--view", help="Response view (default: basic)"),
    with_drafts: bool = typer.Option(False, "--with-drafts", help="Include draft versions in the check"),
    flow_type: str = typer.Option("ALL", "--type", help="FLOW, SUBFLOW, or ALL"),
    output: str = typer.Option("table", "-o", "--output", help="Output format: table|json"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Find flows by what they use (where-used: global vars, EPs, skills, hours)."""
    c = FlowClient(debug=debug)
    params = {"view": view, "flowType": flow_type}
    if with_drafts:
        params["withDraftVersions"] = "yes"
    for key, val in (("globalVar", global_var), ("epId", ep_id),
                     ("skillId", skill_id), ("businessHour", business_hour),
                     ("search", search), ("flowId", flow_id)):
        if val:
            params[key] = val
    if len(params) <= 2 and not with_drafts:
        typer.echo("Error: Provide at least one filter (--global-var, --ep-id, "
                   "--skill-id, --business-hour, --search, or --flow-id).", err=True)
        raise typer.Exit(1)
    data = c.get(f"{c.v1_flows()}:check", params=params)
    items = data if isinstance(data, list) else [data]
    if output == "json":
        print_json(data)
    else:
        from wxcc_flow.main import FLOW_COLUMNS
        print_table(items, FLOW_COLUMNS, limit=0)


def all_versions(
    search: str = typer.Option(None, "--search", help="Filter (searchBy param)"),
    page: int = typer.Option(0, "--page"),
    size: int = typer.Option(10, "--size", help="Page size (versions are large objects — keep small)"),
    latest: bool = typer.Option(False, "--latest",
        help="Use the all-latest endpoint (NOTE: returns 500 on orgs with "
             "never-published flows — verified live on produs1 2026-07-11)"),
    output: str = typer.Option("table", "-o", "--output", help="Output format: table|json"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List flow versions across the whole project."""
    c = FlowClient(debug=debug)
    if latest:
        data = c.get(f"{c.v1_flows()}/versions/all-latest")
    else:
        params = {"page": page, "size": size}
        if search:
            params["searchBy"] = search
        data = c.get(f"{c.v1_flows()}/versions", params=params)
    items = data if isinstance(data, list) else data.get("versions", data.get("items", []))
    if output == "json":
        print_json(data)
    else:
        cols = [("Version ID", "id"), ("Name", "name"), ("Version", "version"),
                ("Type", "flowType"), ("Created", "createdDate")]
        print_table(items, cols, limit=0)


def variable_mapping(
    current_flow_id: str = typer.Argument(..., help="Current flow ID"),
    handoff_flow_id: str = typer.Argument(..., help="Hand-off (GoTo target) flow ID"),
    tag_id: str = typer.Option(None, "--tag-id", help="Hand-off tag ID"),
    source: str = typer.Option(None, "--source", help="Hand-off variable source"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Auto-map variables between a flow and its hand-off (GoTo) flow."""
    c = FlowClient(debug=debug)
    # Contract quirk: orgId is BOTH a path segment and a required query param
    # on this operation — send both.
    params = {"orgId": c.org_id, "currentFlowId": current_flow_id,
              "handOffFlowId": handoff_flow_id}
    if tag_id:
        params["handOffTagId"] = tag_id
    if source:
        params["handOffVariableSource"] = source
    data = c.post(f"{c.v1_flows()}:variable-mapping", params=params)
    print_json(data)


def register(app: typer.Typer) -> None:
    app.command()(patch)
    app.command()(revert)
    app.command("unique-name")(unique_name)
    app.command()(version)
    app.command()(update)
    app.command()(tags)
    app.command("tag-history")(tag_history)
    app.command()(prefs)
    app.command("prefs-set")(prefs_set)
    app.command("prefs-add")(prefs_add)
    app.command("prefs-rm")(prefs_rm)
    app.command()(check)
    app.command("all-versions")(all_versions)
    app.command("variable-mapping")(variable_mapping)
