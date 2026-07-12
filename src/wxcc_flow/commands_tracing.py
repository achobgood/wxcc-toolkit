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
from wxcc_flow.output import print_json

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


def register(app: typer.Typer) -> None:
    app.command()(traces)
