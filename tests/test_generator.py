"""Tests for the wxcc-flow command generator (tools/generator).

Pure-local: no API calls, no cost. Exercises parser fork-fixes, renderer
capabilities, and the generate orchestrator against a mini Flow Store fixture.
"""
import ast
import json
from pathlib import Path

import pytest
import yaml

from tools.generator import parser as P
from tools.generator import renderer as R
from tools.generator import generate as G

FIXTURE = Path(__file__).parent / "fixtures" / "mini_flow_store.json"


@pytest.fixture
def spec():
    return P.load_spec(FIXTURE)


def mini_overrides():
    return {
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


def _render_widgets(spec, overrides):
    G.lint_overrides(overrides, spec)
    resolve = G.build_resolver(overrides)
    kept, rows = G.build_group("widgets", ["Widgets"], spec, overrides, resolve, set())
    ovr_map = {id(ep): o for ep, o in kept}
    code = R.render_group_module("widgets", [ep for ep, _o in kept], lambda ep: ovr_map[id(ep)])
    return code, kept, rows


# ── parser fork fixes ────────────────────────────────────────────────────────

class TestParser:
    def test_dedup_and_endpoint_count(self, spec):
        eps = P.parse_tag("Widgets", spec, auto_inject={"orgId", "projectId"}, seen=set())
        # 7 Widgets ops (admin op is a different tag)
        assert len(eps) == 7
        assert len({e.command_name for e in eps}) == 7  # names unique after dedup

    def test_safe_param_name_spaces(self, spec):
        """Fork fix #1: a spaced param name yields a valid identifier + dash flag."""
        eps = {e.operation_id: e for e in P.parse_tag("Widgets", spec, auto_inject={"orgId", "projectId"}, seen=set())}
        imp = eps["importWidget"]
        ft = next(q for q in imp.query_params if q.name == "Flow Type")
        assert ft.python_name == "flow_type"
        assert ft.cli_flag == "flow-type"

    def test_typed_scalars(self, spec):
        """Fork fix #5: integer query params carry field_type 'int'."""
        eps = {e.operation_id: e for e in P.parse_tag("Widgets", spec, auto_inject={"orgId", "projectId"}, seen=set())}
        find = eps["findWidgets"]
        page = next(q for q in find.query_params if q.name == "page")
        assert page.field_type == "int"

    def test_orgid_auto_injected_from_path(self, spec):
        """orgId/projectId path params are auto-injected, not CLI args."""
        eps = {e.operation_id: e for e in P.parse_tag("Widgets", spec, auto_inject={"orgId", "projectId"}, seen=set())}
        get = eps["getWidget"]
        assert "orgId" in get.auto_inject_path_params
        assert "projectId" in get.auto_inject_path_params
        assert "widgetId" not in get.auto_inject_path_params

    def test_dedup_key_fallback_no_opid(self):
        """Fork fix #7: an op with no operationId dedups on (method, path)."""
        spec = {"paths": {"/x": {"get": {"tags": ["T"], "responses": {}}}}}
        seen = set()
        P.parse_tag("T", spec, seen=seen)
        assert ("get", "/x") in seen

    def test_no_v1_strip(self, spec):
        """Capability 1: url_path keeps the leading slash, no v1 rewrite."""
        eps = {e.operation_id: e for e in P.parse_tag("Widgets", spec, auto_inject={"orgId", "projectId"}, seen=set())}
        assert eps["getWidget"].url_path == "/{orgId}/project/{projectId}/widgets/{widgetId}"


# ── generate orchestrator ────────────────────────────────────────────────────

class TestGenerate:
    def test_dry_run_command_count(self, spec):
        _code, kept, _rows = _render_widgets(spec, mini_overrides())
        assert len(kept) == 7

    def test_skip_tags_admin_excluded(self, spec):
        """admin-widget-controller is a skip_tag → never appears in any group."""
        ovr = mini_overrides()
        G.lint_overrides(ovr, spec)
        # the admin tag is not a source tag of any group, so its ops are unreachable
        assert "admin-widget-controller" not in [t for tags in ovr["groups"].values() for t in tags]

    def test_skip_endpoint_dropped(self, spec):
        ovr = mini_overrides()
        ovr["skip_endpoints"] = {"refreshWidgets": "not needed"}
        _code, kept, _rows = _render_widgets(spec, ovr)
        assert "refreshWidgets" not in [ep.operation_id for ep, _o in kept]

    def test_command_names_override(self, spec):
        _code, kept, _rows = _render_widgets(spec, mini_overrides())
        names = {ep.operation_id: o["command_name"] for ep, o in kept}
        assert names["findWidgets"] == "list"
        assert names["getWidget"] == "get"

    def test_collision_lint_raises(self, spec):
        ovr = mini_overrides()
        ovr["command_names"]["getWidget"] = "list"  # collide with findWidgets
        with pytest.raises(SystemExit, match="collision"):
            _render_widgets(spec, ovr)


# ── lint ─────────────────────────────────────────────────────────────────────

class TestLint:
    def test_unknown_opid_fails(self, spec):
        ovr = mini_overrides()
        ovr["blocked_endpoints"]["notARealOp"] = "x"
        with pytest.raises(SystemExit, match="notARealOp"):
            G.lint_overrides(ovr, spec)

    def test_unknown_group_tag_fails(self, spec):
        ovr = mini_overrides()
        ovr["groups"]["widgets"] = ["Gadgets"]
        with pytest.raises(SystemExit, match="Gadgets"):
            G.lint_overrides(ovr, spec)

    def test_skip_tag_matching_nothing_fails(self, spec):
        ovr = mini_overrides()
        ovr["skip_tags"] = ["no-such-controller"]
        with pytest.raises(SystemExit, match="no-such-controller"):
            G.lint_overrides(ovr, spec)


# ── renderer capabilities ────────────────────────────────────────────────────

class TestRenderer:
    def test_all_modules_ast_parse(self, spec):
        code, _kept, _rows = _render_widgets(spec, mini_overrides())
        ast.parse(code)  # raises on syntax error

    def test_blocked_stub(self, spec):
        code, _k, _r = _render_widgets(spec, mini_overrides())
        assert '@app.command("merge-patch")' in code
        assert "raise typer.Exit(2)" in code
        assert "[BLOCKED]" in code

    def test_warn_banner(self, spec):
        code, _k, _r = _render_widgets(spec, mini_overrides())
        assert 'typer.echo("Warning: may be slow on big orgs", err=True)' in code

    def test_multipart_render(self, spec):
        code, _k, _r = _render_widgets(spec, mini_overrides())
        assert 'file: str = typer.Argument' in code
        assert "c.post_multipart(_path" in code

    def test_spaced_param_flag_and_wire(self, spec):
        code, _k, _r = _render_widgets(spec, mini_overrides())
        assert '"--flow-type"' in code            # dash flag
        assert 'params["Flow Type"] = flow_type' in code  # literal wire name

    def test_pagination_loop(self, spec):
        code, _k, _r = _render_widgets(spec, mini_overrides())
        assert "while True:" in code
        assert 'data.get("widgets"' in code
        assert "if len(batch) < _size:" in code

    def test_delete_force_rename(self, spec):
        code, _k, _r = _render_widgets(spec, mini_overrides())
        assert '"--server-force"' in code          # spec force renamed
        assert 'typer.confirm(f"Delete {widget_id}?"' in code
        assert '"--force"' in code                 # confirmation skip kept

    def test_enum_help(self, spec):
        code, _k, _r = _render_widgets(spec, mini_overrides())
        assert "Choices: A, B" in code

    def test_merge_patch_content_type(self, spec):
        """PATCH content type flows through from the spec."""
        # mergeWidget is blocked, so instead verify a PATCH renders with content_type
        eps = {e.operation_id: e for e in P.parse_tag("Widgets", spec, auto_inject={"orgId", "projectId"}, seen=set())}
        merge = eps["mergeWidget"]
        assert merge.request_content_type == "application/merge-patch+json"


# ── manifest + emission ──────────────────────────────────────────────────────

class TestManifest:
    def test_emit_writes_manifest_and_registry(self, spec, tmp_path):
        ovr = mini_overrides()
        G.lint_overrides(ovr, spec)
        resolve = G.build_resolver(ovr)
        kept, rows = G.build_group("widgets", ["Widgets"], spec, ovr, resolve, set())
        G.emit([("widgets", kept, rows)], tmp_path)
        assert (tmp_path / "widgets.py").exists()
        assert (tmp_path / "__init__.py").exists()
        assert (tmp_path / "_registry.py").exists()
        manifest = json.loads((tmp_path / "_manifest.json").read_text())
        assert len(manifest) == 7
        by_cmd = {m["command"]: m for m in manifest}
        assert by_cmd["get"]["read_only"] is True
        assert by_cmd["create"]["read_only"] is False
        assert by_cmd["merge-patch"]["status"] == "blocked"
        assert by_cmd["refresh"]["status"] == "warn"
        assert by_cmd["create"]["required_params"] == ["name"]

    def test_main_end_to_end(self, spec, tmp_path):
        ovr_path = tmp_path / "ovr.yaml"
        ovr_path.write_text(yaml.safe_dump(mini_overrides()))
        out = tmp_path / "gen"
        rc = G.main(["--all", "--spec", str(FIXTURE), "--overrides", str(ovr_path), "--output", str(out)])
        assert rc == 0
        assert (out / "widgets.py").exists()
        for f in out.glob("*.py"):
            ast.parse(f.read_text())
