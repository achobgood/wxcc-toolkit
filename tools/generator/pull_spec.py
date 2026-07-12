"""Refresh the committed Flow Store spec snapshot from the live contract.

    python3 -m tools.generator.pull_spec            # writes specs/flow-store-api-docs.json
    python3 -m tools.generator.pull_spec --stdout   # print, don't write

The LIVE contract at GET {base}/v3/api-docs is the only source of truth (repo
rule). After pulling, `git diff specs/` shows drift; if any, regenerate + retest.
Token resolution reuses wxcc_flow.config (WXCC_FLOW_TOKEN → WEBEX_ACCESS_TOKEN →
~/.wxcc-flow/config.json).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from wxcc_flow.config import resolve_token, get_base_url

REPO = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = REPO / "specs" / "flow-store-api-docs.json"


def fetch_spec() -> dict:
    token = resolve_token()
    if not token:
        print("No token. Run 'wxcc-flow configure' or set WXCC_FLOW_TOKEN.", file=sys.stderr)
        raise SystemExit(1)
    url = f"{get_base_url()}/v3/api-docs"
    resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if resp.status_code == 401:
        print("401 Unauthorized — regenerate the token at developer.webex.com.", file=sys.stderr)
        raise SystemExit(1)
    resp.raise_for_status()
    return resp.json()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pull the live Flow Store spec into specs/")
    ap.add_argument("--stdout", action="store_true", help="Print the spec instead of writing the snapshot")
    ap.add_argument("--output", default=str(SNAPSHOT))
    args = ap.parse_args(argv)

    spec = fetch_spec()
    n_paths = len(spec.get("paths", {}))
    n_ops = sum(1 for p in spec.get("paths", {}).values()
                for m in ("get", "post", "put", "patch", "delete") if isinstance(p.get(m), dict))
    text = json.dumps(spec, indent=1) + "\n"
    if args.stdout:
        print(text)
    else:
        Path(args.output).write_text(text)
        print(f"Wrote {args.output}  ({n_paths} paths / {n_ops} ops)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())