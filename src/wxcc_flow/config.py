"""Token, org, and project configuration for wxcc-flow."""
import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_PATH = Path.home() / ".wxcc-flow" / "config.json"

BASE_URL = "https://flow-store.produs1.ciscoccservice.com/flow-store"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_config(data: dict, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_token(path: Path = DEFAULT_CONFIG_PATH) -> Optional[str]:
    return load_config(path).get("token")


def get_org_id(path: Path = DEFAULT_CONFIG_PATH) -> Optional[str]:
    return load_config(path).get("org_id")


def get_project_id(path: Path = DEFAULT_CONFIG_PATH) -> Optional[str]:
    return load_config(path).get("project_id")


def get_base_url(path: Path = DEFAULT_CONFIG_PATH) -> str:
    return load_config(path).get("base_url", BASE_URL)


def resolve_token(path: Path = DEFAULT_CONFIG_PATH) -> Optional[str]:
    """Resolve token: WXCC_FLOW_TOKEN env → WEBEX_ACCESS_TOKEN env → config file."""
    token = os.environ.get("WXCC_FLOW_TOKEN")
    if token:
        return token
    token = os.environ.get("WEBEX_ACCESS_TOKEN")
    if token:
        return token
    return get_token(path)
