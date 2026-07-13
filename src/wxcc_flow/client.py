"""REST client for the WxCC Flow Designer API."""
import json
import sys
from typing import Optional

import httpx
import typer

from wxcc_flow.config import resolve_token, get_org_id, get_project_id, get_base_url, save_config, load_config


class FlowStoreError(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


_ERROR_BODY_LIMIT = 2000


def _error_body(resp: httpx.Response) -> str:
    """Error body for display: full text, truncated only past a sane bound
    with an explicit marker (never silently mid-JSON)."""
    if len(resp.text) <= _ERROR_BODY_LIMIT:
        return resp.text
    return resp.text[:_ERROR_BODY_LIMIT] + " …[truncated]"


class FlowClient:
    def __init__(self, debug: bool = False):
        token = resolve_token()
        if not token:
            typer.echo("Error: No token found. Run 'wxcc-flow configure' or set WXCC_FLOW_TOKEN.", err=True)
            raise typer.Exit(1)
        self._token = token
        self._base = get_base_url()
        self._org_id = get_org_id()
        self._project_id = get_project_id()
        self._debug = debug

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    @property
    def org_id(self) -> str:
        if not self._org_id:
            typer.echo("Error: No org_id configured. Run 'wxcc-flow configure'.", err=True)
            raise typer.Exit(1)
        return self._org_id

    @property
    def project_id(self) -> str:
        if self._project_id:
            return self._project_id
        self._project_id = self._resolve_project_id()
        return self._project_id

    def _resolve_project_id(self) -> str:
        """Auto-resolve project ID from userPreferences, then persist."""
        typer.echo("Resolving project ID...", err=True)
        headers = self._headers()
        base = self._base
        oid = self.org_id

        # Primary: userPreferences contains the real project ID
        prefs_url = f"{base}/{oid}/userPreferences"
        resp = httpx.get(prefs_url, headers=headers, timeout=30)
        if resp.is_success and resp.content:
            prefs = self._result(resp)
            pid = prefs.get("projectId") if isinstance(prefs, dict) else None
            if pid:
                cfg = load_config()
                cfg["project_id"] = pid
                save_config(cfg)
                typer.echo(f"Project ID resolved: {pid}", err=True)
                return pid

        # Fallback: list projects, pick first with flows
        url = f"{base}/{oid}/project"
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.is_success:
            data = self._result(resp)
            candidates = [p.get("id") for p in data if p.get("id")] if isinstance(data, list) else []
            for cpid in candidates:
                flows_url = f"{base}/{oid}/project/{cpid}/flows"
                fr = httpx.get(flows_url, headers=headers, params={"size": "1"}, timeout=30)
                if fr.is_success:
                    fdata = self._result(fr)
                    if isinstance(fdata, list):
                        flist = fdata
                    elif isinstance(fdata, dict):
                        flist = fdata.get("flows", fdata.get("items", []))
                    else:
                        flist = []
                    if flist:
                        cfg = load_config()
                        cfg["project_id"] = cpid
                        save_config(cfg)
                        typer.echo(f"Project ID resolved: {cpid}", err=True)
                        return cpid
            if candidates:
                cfg = load_config()
                cfg["project_id"] = candidates[0]
                save_config(cfg)
                typer.echo(f"Project ID resolved: {candidates[0]}", err=True)
                return candidates[0]

        typer.echo("Error: Could not resolve project ID. Use 'wxcc-flow set-project ID'.", err=True)
        raise typer.Exit(1)

    def _url(self, path: str) -> str:
        """Build full URL, injecting orgId and projectId only when present in path."""
        if "{orgId}" in path:
            path = path.replace("{orgId}", self.org_id)
        if "{projectId}" in path:
            path = path.replace("{projectId}", self.project_id)
        return f"{self._base}{path}"

    def _log_request(self, method: str, url: str, body=None):
        if self._debug:
            typer.echo(f">>> {method} {url}", err=True)
            if body:
                typer.echo(f">>> Body: {json.dumps(body, indent=2)[:500]}", err=True)

    def _log_response(self, resp: httpx.Response):
        if self._debug:
            typer.echo(f"<<< {resp.status_code}", err=True)
            if resp.content:
                typer.echo(f"<<< {resp.text[:500]}", err=True)

    @staticmethod
    def _result(resp: httpx.Response):
        """Parse a success body as JSON, tolerating non-JSON bodies.

        Some Flow Store endpoints return plain text on success (e.g. /health,
        lock/unlock). Guarding json() here prevents the transient traceback class
        found live 2026-07-12 (unguarded resp.json() on a non-JSON body).
        """
        if not resp.content:
            return {}
        try:
            return resp.json()
        except (ValueError, json.JSONDecodeError):
            return resp.text

    def _handle_error(self, resp: httpx.Response):
        if resp.status_code == 401:
            typer.echo("Error: Authentication failed (401). Token may be expired — regenerate at developer.webex.com.", err=True)
            raise typer.Exit(1)
        if resp.status_code == 403:
            typer.echo("Error: Forbidden (403). Check org permissions.", err=True)
            raise typer.Exit(1)
        if resp.status_code == 400:
            raise FlowStoreError(400, resp.text)
        if resp.status_code == 404:
            typer.echo(f"Error: Not found (404). {_error_body(resp)}", err=True)
            raise typer.Exit(1)
        if not resp.is_success:
            typer.echo(f"Error: HTTP {resp.status_code}: {_error_body(resp)}", err=True)
            raise typer.Exit(1)

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        url = self._url(path)
        self._log_request("GET", url)
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=30)
        self._log_response(resp)
        self._handle_error(resp)
        return self._result(resp)

    def get_safe(self, path: str, params: Optional[dict] = None):
        """GET that returns (data, None) on success or (None, status) on error.

        Does not print error messages or raise — caller handles failures.
        """
        url = self._url(path)
        self._log_request("GET", url)
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=30)
        self._log_response(resp)
        if not resp.is_success:
            return None, resp.status_code
        return self._result(resp), None

    def post(self, path: str, json_body=None, params: Optional[dict] = None) -> dict:
        url = self._url(path)
        self._log_request("POST", url, json_body)
        resp = httpx.post(url, headers=self._headers(), json=json_body, params=params, timeout=60)
        self._log_response(resp)
        self._handle_error(resp)
        return self._result(resp)

    def put(self, path: str, json_body=None, params: Optional[dict] = None) -> dict:
        url = self._url(path)
        self._log_request("PUT", url, json_body)
        resp = httpx.put(url, headers=self._headers(), json=json_body, params=params, timeout=60)
        self._log_response(resp)
        self._handle_error(resp)
        return self._result(resp)

    def patch(self, path: str, json_body=None, params: Optional[dict] = None,
              content_type: str = "application/json") -> dict:
        """PATCH with a configurable content type.

        v2 patchDraft takes plain application/json; v1 mergePatchFlow takes
        application/merge-patch+json.
        """
        url = self._url(path)
        self._log_request("PATCH", url, json_body)
        headers = self._headers()
        headers["Content-Type"] = content_type
        resp = httpx.patch(url, headers=headers, content=json.dumps(json_body),
                           params=params, timeout=60)
        self._log_response(resp)
        self._handle_error(resp)
        return self._result(resp)

    def post_multipart(self, path: str, filename: str, content: bytes,
                       params: Optional[dict] = None) -> dict:
        """POST a file as a multipart 'file' part (v1 flows:import).

        The live contract's requestBody for importFlowVersion_1 is
        {file: binary} — sending raw JSON instead 500s with
        "Oops... Something broke..." (verified 2026-07-11).
        """
        url = self._url(path)
        self._log_request("POST", url)
        headers = {"Authorization": f"Bearer {self._token}"}  # no Content-Type: httpx sets the multipart boundary
        resp = httpx.post(url, headers=headers, params=params,
                          files={"file": (filename, content, "application/json")},
                          timeout=60)
        self._log_response(resp)
        self._handle_error(resp)
        return self._result(resp)

    def delete_with_body(self, path: str, json_body=None) -> dict:
        """DELETE with a JSON body (flow preferences delete takes a name list)."""
        url = self._url(path)
        self._log_request("DELETE", url, json_body)
        resp = httpx.request("DELETE", url, headers=self._headers(),
                             json=json_body, timeout=30)
        self._log_response(resp)
        self._handle_error(resp)
        return self._result(resp)

    def delete(self, path: str, params: Optional[dict] = None) -> dict:
        url = self._url(path)
        self._log_request("DELETE", url)
        resp = httpx.delete(url, headers=self._headers(), params=params, timeout=30)
        self._log_response(resp)
        self._handle_error(resp)
        return self._result(resp)

    def get_text(self, path: str) -> str:
        """GET that returns raw text (for health endpoint)."""
        url = self._url(path)
        self._log_request("GET", url)
        resp = httpx.get(url, headers=self._headers(), timeout=30)
        self._log_response(resp)
        self._handle_error(resp)
        return resp.text

    # --- Convenience path builders ---

    def v1_flows(self) -> str:
        return f"/{self.org_id}/project/{self.project_id}/flows"

    def v1_flow(self, flow_id: str) -> str:
        return f"/{self.org_id}/project/{self.project_id}/flows/{flow_id}"

    # ⚠️ PATH STRUCTURE — DO NOT "FIX" BACK. The `v2` segment comes AFTER
    # project/{projectId}, NOT before {orgId}. The intuitive-looking
    # `/v2/{org}/project/{proj}/...` form is what the CLI shipped with and it
    # 500s on prod — a 500 here means the path is UNROUTED, not a server bug.
    # If these ops ever 500/404 again, the paths moved: re-pull the LIVE
    # contract `GET {base}/v3/api-docs` and diff, don't theorize. (This exact
    # mismatch cost hours on 2026-07-11.)
    def v2_flows(self) -> str:
        return f"/{self.org_id}/project/{self.project_id}/v2/flows"

    def v2_flow(self, flow_id: str) -> str:
        return f"/{self.org_id}/project/{self.project_id}/v2/flows/{flow_id}"

    def v2_activities(self) -> str:
        return f"/{self.org_id}/project/{self.project_id}/v2/activities"

    def get_activity_definition(self, name: str, flow_type: str = "FLOW") -> dict:
        """Fetch the full activity definition from the activities list endpoint.

        Prod returns a flat list of activities keyed by `activityName`. (Older
        deployments returned a dict keyed by category with a `name` field —
        handled for back-compat.)
        """
        data = self.get(self.v2_activities(), params={"flowType": flow_type})
        if isinstance(data, list):
            for act in data:
                if isinstance(act, dict) and act.get("activityName") == name:
                    return act
        elif isinstance(data, dict):
            for category, activity_list in data.items():
                if isinstance(activity_list, list):
                    for act in activity_list:
                        if act.get("activityName") == name or act.get("name") == name:
                            act.setdefault("category", category)
                            return act
        typer.echo(f"Error: Activity '{name}' not found in the registry.", err=True)
        raise typer.Exit(1)
