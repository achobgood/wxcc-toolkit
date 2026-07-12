"""Flow Tracing API commands — interactions, traces, analytics.

These read the observability side of the Flow Store: which calls hit a flow
(interactions), what each call did step-by-step (traces), and aggregate
counts (analytics). The Flow Store does NOT place calls — interaction data
only exists after a real contact was routed through the flow (entry point →
dialed call). With no data these endpoints return empty pages, which the
commands report honestly.
"""
import typer

from wxcc_flow.client import FlowClient
from wxcc_flow.output import print_json, print_table

INTERACTION_COLUMNS = [
    ("Interaction ID", "interactionId"),
    ("Version", "flowVersionId"),
    ("ANI", "ani"),
    ("DNIS", "dnis"),
    ("Start", "startTime"),
    ("End", "endTime"),
]


def interactions(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    from_ms: int = typer.Option(None, "--from", help="Start of window (epoch milliseconds)"),
    to_ms: int = typer.Option(None, "--to", help="End of window (epoch milliseconds)"),
    search: str = typer.Option(None, "--search", help="Search by ANI, DNIS, or interaction ID"),
    interaction_id: str = typer.Option(None, "--interaction-id", help="Filter to a single interaction"),
    version_id: str = typer.Option(None, "--version-id", help="Filter to a flow version ID"),
    tag_ids: str = typer.Option(None, "--tag-ids", help="Comma-separated tag IDs"),
    activity_id: str = typer.Option(None, "--activity-id", help="Only interactions touching this activity diagram ID"),
    page: int = typer.Option(0, "--page"),
    page_size: int = typer.Option(100, "--page-size"),
    output: str = typer.Option("table", "-o", "--output", help="Output format: table|json"),
    debug: bool = typer.Option(False, "--debug"),
):
    """List interactions (real calls) that hit a flow, across its versions."""
    c = FlowClient(debug=debug)
    params = {"currentPage": page, "pageSize": page_size}
    if from_ms is not None:
        params["from"] = from_ms
    if to_ms is not None:
        params["to"] = to_ms
    for key, val in (("search", search), ("interactionId", interaction_id),
                     ("versionId", version_id), ("tagIds", tag_ids),
                     ("activityDiagramId", activity_id)):
        if val:
            params[key] = val
    data = c.get(f"{c.v1_flow(flow_id)}/interactions", params=params)
    items = data.get("interactions", []) if isinstance(data, dict) else data
    page_info = data.get("pageInfo", {}) if isinstance(data, dict) else {}
    if output == "json":
        print_json(data)
        return
    if not items:
        typer.echo("No interactions recorded for this flow (no real call has "
                   "been routed through it in the queried window).")
        return
    print_table(items, INTERACTION_COLUMNS, limit=0)
    if page_info:
        typer.echo(f"Page {page_info.get('currentPage')} of {page_info.get('totalPages')} "
                   f"({page_info.get('totalRecords')} total)")


def interaction(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    version_id: str = typer.Argument(..., help="Flow version ID"),
    interaction_id: str = typer.Argument(..., help="Interaction ID"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get metadata for one interaction of a flow version."""
    c = FlowClient(debug=debug)
    data = c.get(f"{c.v1_flow(flow_id)}/versions/{version_id}"
                 f"/interaction/{interaction_id}")
    print_json(data)


def traces(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    version_id: str = typer.Argument(..., help="Flow version ID"),
    interaction_id: str = typer.Argument(..., help="Interaction ID"),
    decrypt: bool = typer.Option(False, "--decrypt", help="Fetch decrypted traces (requires --process-id)"),
    process_id: str = typer.Option(None, "--process-id", help="processId of the flow version (required with --decrypt)"),
    doc_id: str = typer.Option(None, "--doc-id", help="Document ID of the flow trace"),
    page: int = typer.Option(0, "--page"),
    page_size: int = typer.Option(100, "--page-size"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get step-by-step traces for one interaction of a flow version."""
    c = FlowClient(debug=debug)
    base = (f"{c.v1_flow(flow_id)}/versions/{version_id}"
            f"/interaction/{interaction_id}/traces")
    if decrypt:
        # traces:decrypt requires processId as a query param (contract: REQ).
        if not process_id:
            typer.echo("Error: --decrypt requires --process-id (get it from the "
                       "undecrypted traces or the interaction metadata).", err=True)
            raise typer.Exit(1)
        params = {"processId": process_id}
        if doc_id:
            params["docId"] = doc_id
        data = c.get(f"{base}:decrypt", params=params)
    else:
        params = {"currentPage": page, "pageSize": page_size}
        if process_id:
            params["processId"] = process_id
        if doc_id:
            params["docId"] = doc_id
        data = c.get(base, params=params)
    print_json(data)


def analytics(
    flow_id: str = typer.Argument(..., help="Flow ID"),
    version_id: str = typer.Argument(..., help="Flow version ID"),
    start: int = typer.Option(None, "--start", help="Start of window (epoch milliseconds)"),
    end: int = typer.Option(None, "--end", help="End of window (epoch milliseconds)"),
    debug: bool = typer.Option(False, "--debug"),
):
    """Get aggregate analytics for a flow version."""
    c = FlowClient(debug=debug)
    params = {}
    if start is not None:
        params["startTime"] = start
    if end is not None:
        params["endTime"] = end
    data = c.get(f"{c.v1_flow(flow_id)}/versions/{version_id}/analytics",
                 params=params or None)
    print_json(data)


def register(app: typer.Typer) -> None:
    app.command()(interactions)
    app.command()(interaction)
    app.command()(traces)
    app.command()(analytics)
