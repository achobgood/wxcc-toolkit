"""Best-effort PyPI update check for the wxcc-flow CLI.

Runs once per invocation from the top-level Typer callback. It must NEVER
block or break a real command, so every path here is defensive:

* a short (1s) network timeout,
* a 24h on-disk cache next to the config (``~/.wxcc-flow/update-check.json``),
* every exception (no network, PyPI outage, bad JSON, unwritable cache)
  swallowed — a failure prints nothing and returns ``None``.

The notice is printed to stderr so it never corrupts ``-o json`` output on
stdout. It is silenced by ``--no-update-check``, by ``WXCC_FLOW_NO_UPDATE_CHECK``,
and under ``CI`` (so pipelines and the test suite stay hermetic).
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

PACKAGE_NAME = "wxcc-toolkit"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
CACHE_PATH = Path.home() / ".wxcc-flow" / "update-check.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # re-check PyPI at most once a day
REQUEST_TIMEOUT_SECONDS = 1.0
ENV_DISABLE = "WXCC_FLOW_NO_UPDATE_CHECK"

_LEADING_NUMERIC = re.compile(r"(\d+(?:\.\d+)*)")


def _parse_version(text):
    """Leading numeric components of a version as an int tuple.

    ``'0.3.10'`` -> ``(0, 3, 10)``; ``'0.4.0rc1'`` -> ``(0, 4, 0)``;
    ``''`` / unparseable -> ``()``. Dependency-free so we don't pull in
    ``packaging`` (not a declared runtime dep).
    """
    if not text:
        return ()
    m = _LEADING_NUMERIC.match(text.strip())
    if not m:
        return ()
    return tuple(int(p) for p in m.group(1).split("."))


def _is_newer(latest, current):
    """True iff ``latest`` is a strictly newer release than ``current``."""
    lt, ct = _parse_version(latest), _parse_version(current)
    if not lt:
        return False
    width = max(len(lt), len(ct))
    lt = lt + (0,) * (width - len(lt))
    ct = ct + (0,) * (width - len(ct))
    return lt > ct


def _env_truthy(name):
    val = os.environ.get(name, "").strip().lower()
    return bool(val) and val not in ("0", "false", "no", "off")


def _read_cache(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(path, latest, now):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"pkg": PACKAGE_NAME, "latest": latest, "last_check": now}, f)
    except Exception:
        pass


def _fetch_latest(timeout):
    resp = httpx.get(PYPI_JSON_URL, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["info"]["version"]


def check_for_update(current_version, *, now=None, cache_path=CACHE_PATH,
                     ttl=CACHE_TTL_SECONDS, timeout=REQUEST_TIMEOUT_SECONDS,
                     force=False):
    """Return the latest PyPI version string if newer than ``current_version``.

    Returns ``None`` when already up to date OR on any failure. Only hits PyPI
    when the cache is missing/stale or ``force=True``; a fresh cache answers
    offline.
    """
    try:
        if now is None:
            now = time.time()
        latest = None
        cache = _read_cache(cache_path)
        if (not force and cache
                and isinstance(cache.get("last_check"), (int, float))
                and now - cache["last_check"] < ttl):
            latest = cache.get("latest")
        if latest is None:
            latest = _fetch_latest(timeout)
            _write_cache(cache_path, latest, now)
        if latest and _is_newer(latest, current_version):
            return latest
        return None
    except Exception:
        return None


def maybe_notify_update(current_version, *, disabled=False, stream=None, **kwargs):
    """Print a one-line upgrade notice to stderr if a newer release exists.

    Silent when disabled (flag, ``WXCC_FLOW_NO_UPDATE_CHECK``, or ``CI``) and
    silent on any failure. Returns the latest version if a notice was printed,
    else ``None``. Extra kwargs pass through to :func:`check_for_update`.
    """
    if disabled or _env_truthy(ENV_DISABLE) or _env_truthy("CI"):
        return None
    latest = check_for_update(current_version, **kwargs)
    if not latest:
        return None
    try:
        (stream or sys.stderr).write(
            f"wxcc-flow {latest} available (you have {current_version}). "
            f"Upgrade: pip install -U {PACKAGE_NAME} && wxcc-flow init\n"
        )
    except Exception:
        return None
    return latest
