"""Golden-file regression test for the generator.

Renders the mini Flow Store fixture's Widgets group and byte-compares it against
tests/fixtures/expected_widgets.py. A diff means the emitter changed — inspect,
then regenerate the golden if the change is intended:

    python3 -c "from tests.test_generator_regression import render_widgets; \
        open('tests/fixtures/expected_widgets.py','w').write(render_widgets())"
"""
import ast
import difflib
from pathlib import Path

from tools.generator import parser as P
from tools.generator import renderer as R
from tools.generator import generate as G

FIXTURE = Path(__file__).parent / "fixtures" / "mini_flow_store.json"
GOLDEN = Path(__file__).parent / "fixtures" / "expected_widgets.py"

_OVERRIDES = {
    "groups": {"widgets": ["Widgets"]},
    "skip_tags": ["admin-widget-controller"],
    "auto_inject_from_config": ["orgId", "projectId"],
    "blocked_endpoints": {"mergeWidget": "no-op; use update"},
    "warn_endpoints": {"refreshWidgets": "may be slow on big orgs"},
    "request_overrides": {"importWidget": {"multipart": True}},
    "param_cli_names": {"importWidget": {"Flow Type": "flow-type"}},
    "pagination": {"findWidgets": {"page_param": "page", "size_param": "size", "item_key": "widgets"}},
    "table_columns": {"findWidgets": [["ID", "id"], ["Name", "name"]]},
    "command_names": {
        "findWidgets": "list", "getWidget": "get", "createWidget": "create",
        "deleteWidget": "delete", "importWidget": "import",
        "mergeWidget": "merge-patch", "refreshWidgets": "refresh",
    },
}


def render_widgets() -> str:
    spec = P.load_spec(FIXTURE)
    G.lint_overrides(_OVERRIDES, spec)
    resolve = G.build_resolver(_OVERRIDES)
    kept, _rows = G.build_group("widgets", ["Widgets"], spec, _OVERRIDES, resolve, set())
    ovr_map = {id(ep): o for ep, o in kept}
    return R.render_group_module("widgets", [ep for ep, _o in kept], lambda ep: ovr_map[id(ep)])


def test_golden_matches():
    actual = render_widgets()
    expected = GOLDEN.read_text()
    if actual != expected:
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), actual.splitlines(),
            fromfile="expected_widgets.py", tofile="rendered", lineterm=""))
        raise AssertionError("Generated output drifted from the golden:\n" + diff)


def test_golden_is_valid_python():
    ast.parse(GOLDEN.read_text())


def test_rendered_is_valid_python():
    ast.parse(render_widgets())
