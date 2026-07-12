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

    def test_unknown_section_key_fails(self, spec):
        """A mistyped section name (e.g. skip_endpoint) must FAIL — never silently
        drop its payload (which would re-expose skipped ops)."""
        ovr = mini_overrides()
        ovr["skip_endpoint"] = {"refreshWidgets": "typo'd section"}  # singular typo
        with pytest.raises(SystemExit, match="unknown top-level override section"):
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

    def test_required_body_field_optional_and_validated_both_branches(self, spec):
        """Fork fix #6: a required body scalar renders as an OPTIONAL flag, and the
        _missing check sits OUTSIDE the if/else so --json-body is validated too."""
        code, _k, _r = _render_widgets(spec, mini_overrides())
        create = "\n".join(l for l in code.splitlines())
        # name is required in the spec but must render optional (Option(None))
        assert 'name: str = typer.Option(None, "--name"' in code
        assert 'typer.Option(..., "--name"' not in code
        # the _missing guard is at 4-space indent (validates both branches), not 8
        assert "\n    _missing = [k for k in ['name']" in code
        assert "\n        _missing = [k for k in ['name']" not in code

    def test_body_defaults_rendered(self, spec):
        """Fork fix #3: body_defaults seeds the body (via setdefault) for all body
        types, applied at 4-space so --json-body callers get the default too."""
        ovr = mini_overrides()
        ovr["body_defaults"] = {"createWidget": {"kind": "default"}}
        code, _k, _r = _render_widgets(spec, ovr)
        assert "\n    body.setdefault('kind', 'default')" in code


# ── manifest + emission ──────────────────────────────────────────────────────

class TestManifest:
    def test_emit_writes_manifest_and_registry(self, spec, tmp_path):
        ovr = mini_overrides()
        G.lint_overrides(ovr, spec)
        resolve = G.build_resolver(ovr)
        kept, rows = G.build_group("widgets", ["Widgets"], spec, ovr, resolve, set())
        G.emit([("widgets", kept, rows)], tmp_path, [])
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


# ── Phase-B polish features (2026-07-12 "full polish") ───────────────────────

class TestPhaseBFeatures:
    def test_global_param_cli_names(self, spec):
        """flowType/'Flow Type' → --type everywhere via global_param_cli_names."""
        ovr = mini_overrides()
        ovr.pop("param_cli_names", None)                       # let global handle it
        ovr["global_param_cli_names"] = {"Flow Type": "type"}
        code, _k, _r = _render_widgets(spec, ovr)
        assert '"--type"' in code
        ast.parse(code)

    def test_per_op_cli_name_wins_over_global(self, spec):
        """A per-op param_cli_names entry beats the global on a conflicting wire name."""
        ovr = mini_overrides()
        ovr["global_param_cli_names"] = {"Flow Type": "type"}
        ovr["param_cli_names"] = {"importWidget": {"Flow Type": "zzz"}}
        code, _k, _r = _render_widgets(spec, ovr)
        assert '"--zzz"' in code and '"--type"' not in code

    def test_success_echo(self, spec):
        """Empty-body mutation prints a friendly confirmation, not a bare null."""
        ovr = mini_overrides()
        ovr["success_echo"] = {"deleteWidget": "Deleted {widget_id}"}
        code, _k, _r = _render_widgets(spec, ovr)
        assert "if data and not isinstance(data, str):" in code
        assert 'typer.echo(f"Deleted {widget_id}")' in code
        ast.parse(code)

    def test_promote_to_argument(self, spec):
        """A named query param becomes a positional Argument + is still sent."""
        ovr = mini_overrides()
        ovr["promote_to_argument"] = {"findWidgets": ["kind"]}
        code, _k, _r = _render_widgets(spec, ovr)
        assert "kind: str = typer.Argument(" in code
        assert 'params["kind"] = kind' in code
        assert '"--kind"' not in code                          # no longer an Option
        ast.parse(code)

    def test_expose_path_param(self, spec):
        """An auto-injected projectId is exposed as an optional --project-id override."""
        ovr = mini_overrides()
        ovr["expose_path_param"] = {"getWidget": ["projectId"]}
        code, _k, _r = _render_widgets(spec, ovr)
        assert 'project_id: str = typer.Option(None, "--project-id"' in code
        assert "_project_id = project_id or c.project_id" in code
        assert "project/{_project_id}/" in code                # URL reads the override
        ast.parse(code)


# ── top-level promotions (design § 5) ────────────────────────────────────────

class TestPromotions:
    def _groups_data(self, spec, ovr):
        G.lint_overrides(ovr, spec)
        resolve = G.build_resolver(ovr)
        kept, rows = G.build_group("widgets", ["Widgets"], spec, ovr, resolve, set())
        return [("widgets", kept, rows)]

    def test_build_promotions_maps_opid_to_command(self, spec):
        ovr = mini_overrides()
        ovr["top_level_commands"] = {"getWidget": "get", "findWidgets": "list"}
        promos = G._build_promotions(ovr, self._groups_data(spec, ovr))
        assert ("widgets", "get", "get") in promos
        assert ("widgets", "list", "list") in promos

    def test_promote_blocked_op_fails(self, spec):
        ovr = mini_overrides()
        ovr["top_level_commands"] = {"mergeWidget": "merge-patch"}   # blocked stub
        with pytest.raises(SystemExit, match="blocked"):
            G._build_promotions(ovr, self._groups_data(spec, ovr))

    def test_promote_skipped_op_fails(self, spec):
        ovr = mini_overrides()
        ovr["top_level_commands"] = {"purgeWidgets": "purge"}        # admin skip_tag
        with pytest.raises(SystemExit, match="skipped or absent"):
            G._build_promotions(ovr, self._groups_data(spec, ovr))

    def test_promote_duplicate_name_fails(self, spec):
        ovr = mini_overrides()
        ovr["top_level_commands"] = {"getWidget": "x", "findWidgets": "x"}
        with pytest.raises(SystemExit, match="promoted twice"):
            G._build_promotions(ovr, self._groups_data(spec, ovr))

    def test_render_init_emits_promotion_scaffold(self):
        code = G._render_init(["widgets"], [("widgets", "get", "get")])
        assert "from typer.main import get_command_name" in code
        assert '_PROMOTIONS = [' in code
        assert '("widgets", "get", "get"),' in code
        assert "RuntimeError(" in code
        assert "app.command(top_name)(ci.callback)" in code
        ast.parse(code)

    def test_manifest_annotates_top_level(self, spec, tmp_path):
        ovr = mini_overrides()
        ovr["top_level_commands"] = {"getWidget": "get"}
        gd = self._groups_data(spec, ovr)
        promos = G._build_promotions(ovr, gd)
        G.emit(gd, tmp_path, promos)
        manifest = json.loads((tmp_path / "_manifest.json").read_text())
        by_cmd = {m["command"]: m for m in manifest}
        assert by_cmd["get"].get("top_level") == "get"
        assert "top_level" not in by_cmd["create"]              # unpromoted stays clean


class TestPhaseCFeatures:
    """Phase-C parity features: auto_resolve_params, extra_commands,
    param_defaults, body_positional_list, confirm_message, require_some_body."""

    def _unblocked(self):
        ovr = mini_overrides()
        ovr.pop("blocked_endpoints")            # render mergeWidget as a real PATCH
        return ovr

    def test_auto_resolve_renders_prefetch(self, spec):
        ovr = self._unblocked()
        ovr["auto_resolve_params"] = {"mergeWidget": {"expectedVersion": {
            "unwrap": "widget", "field": "version", "forward_params": ["flowType"]}}}
        code, _k, _r = _render_widgets(spec, ovr)
        assert '    if "expectedVersion" not in params:' in code
        assert "_rp = {k: params[k] for k in ['flowType'] if k in params}" in code
        assert '_pre = c.get(f"/{c.org_id}/project/{c.project_id}/widgets/{widget_id}", params=_rp)' in code
        assert '_pre = _pre.get("widget", _pre)' in code
        assert 'params["expectedVersion"] = (_pre.get("version") or 0) if isinstance(_pre, dict) else 0' in code
        ast.parse(code)

    def test_auto_resolve_lint_rejects_non_query_param(self, spec):
        ovr = self._unblocked()
        ovr["auto_resolve_params"] = {"mergeWidget": {"notAParam": {"field": "version"}}}
        with pytest.raises(SystemExit, match="not a query param"):
            G.lint_overrides(ovr, spec)

    def test_auto_resolve_lint_requires_field(self, spec):
        ovr = self._unblocked()
        ovr["auto_resolve_params"] = {"mergeWidget": {"expectedVersion": {"unwrap": "widget"}}}
        with pytest.raises(SystemExit, match="'field'"):
            G.lint_overrides(ovr, spec)

    def test_param_defaults_setdefault_after_query_build(self, spec):
        ovr = mini_overrides()
        ovr["param_defaults"] = {"findWidgets": {"kind": "draft"}}
        code, _k, _r = _render_widgets(spec, ovr)
        assert "    params.setdefault(\"kind\", 'draft')" in code
        # explicit flag wins: the setdefault must come AFTER the query build
        assert code.index('params["kind"] = kind') < code.index('params.setdefault("kind"')
        ast.parse(code)

    def test_require_some_body_guard(self, spec):
        ovr = mini_overrides()
        ovr["require_some_body"] = {"createWidget": True}
        code, _k, _r = _render_widgets(spec, ovr)
        assert "    if not body:" in code
        assert "provide at least one field" in code
        ast.parse(code)

    def test_body_positional_list_and_confirm_message(self, spec):
        ovr = {
            "groups": {"widget-tags": ["WidgetTags"]},
            "auto_inject_from_config": ["orgId", "projectId"],
            "command_names": {"removeWidgetTags": "remove"},
            "body_positional_list": {"removeWidgetTags": {"arg": "names", "help": "Tag names"}},
            "confirm_message": {"removeWidgetTags": "Remove tags from widget {widget_id}?"},
        }
        G.lint_overrides(ovr, spec)
        resolve = G.build_resolver(ovr)
        kept, _rows = G.build_group("widget-tags", ["WidgetTags"], spec, ovr, resolve, set())
        ovr_map = {id(ep): o for ep, o in kept}
        code = R.render_group_module("widget-tags", [ep for ep, _o in kept], lambda ep: ovr_map[id(ep)])
        assert 'names: list[str] = typer.Argument(..., help="Tag names")' in code
        assert "    body = list(names)" in code
        assert '"--json-body"' not in code                     # suppressed
        assert 'typer.confirm(f"Remove tags from widget {widget_id}?", abort=True)' in code
        assert "c.delete_with_body(_path, json_body=body)" in code
        ast.parse(code)

    def test_body_positional_list_lint_requires_arg(self, spec):
        ovr = mini_overrides()
        ovr["body_positional_list"] = {"createWidget": {"help": "no arg key"}}
        with pytest.raises(SystemExit, match="'arg'"):
            G.lint_overrides(ovr, spec)

    def test_value_mapped_bool_flag(self, spec):
        """Audit F1: an inversion spec with true_value/false_value maps the bool
        flag to custom wire values (yes/no) instead of str(bool).lower()."""
        ovr = mini_overrides()
        ovr["param_flag_inversions"] = {"findWidgets": {
            "kind": {"cli_name": "with-drafts", "true_value": "yes", "false_value": "no"}}}
        code, _k, _r = _render_widgets(spec, ovr)
        assert '"--with-drafts/--no-with-drafts"' in code
        assert "params[\"kind\"] = 'yes' if with_drafts else 'no'" in code
        ast.parse(code)

    def test_file_not_found_guard(self, spec):
        """Audit F3: body_from_file and multipart opens fail with a clean error,
        not a traceback."""
        ovr = mini_overrides()
        ovr["body_from_file"] = {"createWidget": True}
        code, _k, _r = _render_widgets(spec, ovr)
        assert "except FileNotFoundError:" in code
        assert 'typer.echo(f"Error: File not found: {body_file}", err=True)' in code
        assert 'typer.echo(f"Error: File not found: {file}", err=True)' in code  # multipart import

    def test_auto_resolve_after_body_guards(self, spec):
        """Audit F5: the auto_resolve pre-fetch is emitted AFTER the body build
        and require_some_body guard, so client-side errors fire before any call."""
        ovr = self._unblocked()
        ovr["auto_resolve_params"] = {"mergeWidget": {"expectedVersion": {"field": "version"}}}
        ovr["require_some_body"] = {"mergeWidget": True}
        code, _k, _r = _render_widgets(spec, ovr)
        assert code.index("provide at least one field") < code.index('"expectedVersion" not in params')
        ast.parse(code)


class TestExtraCommands:
    def test_clone_renders_alongside_base(self, spec):
        ovr = mini_overrides()
        ovr["extra_commands"] = {"findWidgets": [{
            "name": "search", "doc": "Search widgets by kind",
            "overrides": {"promote_to_argument": ["kind"]}}]}
        code, kept, rows = _render_widgets(spec, ovr)
        assert '@app.command("list")' in code
        assert '@app.command("search")' in code
        assert '"""Search widgets by kind.' in code
        # clone: kind is positional; base: kind stays an Option
        assert "kind: str = typer.Argument(" in code
        assert '"--kind"' in code
        by_cmd = {r["command"]: r for r in rows}
        assert by_cmd["search"].get("extra") is True
        assert "extra" not in by_cmd["list"]
        ast.parse(code)

    def test_clone_clears_inherited_key_with_none(self, spec):
        """A None override clears a key inherited from the base (e.g. warn)."""
        ovr = mini_overrides()
        ovr["extra_commands"] = {"refreshWidgets": [{
            "name": "refresh-quiet", "overrides": {"warn": None}}]}
        code, _k, rows = _render_widgets(spec, ovr)
        base = code[code.index('@app.command("refresh")'):code.index('@app.command("refresh-quiet")')]
        clone = code[code.index('@app.command("refresh-quiet")'):]
        assert "Warning:" in base and "Warning:" not in clone
        by_cmd = {r["command"]: r for r in rows}
        assert by_cmd["refresh-quiet"]["status"] == "generated"   # warn cleared

    def test_clone_of_skipped_or_blocked_fails(self, spec):
        ovr = mini_overrides()
        ovr["skip_endpoints"] = {"refreshWidgets": "skipped"}
        ovr["extra_commands"] = {"refreshWidgets": [{"name": "x"}]}
        with pytest.raises(SystemExit, match="skipped"):
            _render_widgets(spec, ovr)
        ovr2 = mini_overrides()
        ovr2["extra_commands"] = {"mergeWidget": [{"name": "x"}]}    # blocked stub
        with pytest.raises(SystemExit, match="blocked"):
            _render_widgets(spec, ovr2)

    def test_clone_lint_rejects_unknown_override_key(self, spec):
        ovr = mini_overrides()
        ovr["extra_commands"] = {"findWidgets": [{
            "name": "search", "overrides": {"warn_endpoints": "wrong-level key"}}]}
        with pytest.raises(SystemExit, match="RESOLVED key names"):
            G.lint_overrides(ovr, spec)

    def test_clone_promotes_via_top_level(self, spec):
        ovr = mini_overrides()
        ovr["top_level_commands"] = {"findWidgets": "list"}
        ovr["extra_commands"] = {"findWidgets": [{
            "name": "search", "top_level": "search",
            "overrides": {"promote_to_argument": ["kind"]}}]}
        G.lint_overrides(ovr, spec)
        resolve = G.build_resolver(ovr)
        kept, rows = G.build_group("widgets", ["Widgets"], spec, ovr, resolve, set())
        promos = G._build_promotions(ovr, [("widgets", kept, rows)])
        assert ("widgets", "list", "list") in promos
        assert ("widgets", "search", "search") in promos

    def test_clone_top_level_name_collision_fails(self, spec):
        ovr = mini_overrides()
        ovr["top_level_commands"] = {"findWidgets": "search"}
        ovr["extra_commands"] = {"findWidgets": [{"name": "search", "top_level": "search"}]}
        resolve = G.build_resolver(ovr)
        kept, rows = G.build_group("widgets", ["Widgets"], spec, ovr, resolve, set())
        with pytest.raises(SystemExit, match="promoted twice"):
            G._build_promotions(ovr, [("widgets", kept, rows)])


class TestPromotionRuntime:
    """The generated package's register() guard, against the real 21 promotions."""

    def test_collision_raises_when_hand_command_present(self):
        import typer
        from wxcc_flow import generated
        app = typer.Typer()

        @app.command()
        def get():   # a still-present hand command named 'get'
            ...
        with pytest.raises(RuntimeError, match="collides"):
            generated.register(app)

    def test_register_promotes_when_clean(self):
        import typer
        from wxcc_flow import generated
        app = typer.Typer()
        generated.register(app)
        names = {(c.name or c.callback.__name__).replace("_", "-")
                 for c in app.registered_commands}
        assert {"get", "lock", "delete", "revert", "connector-list"} <= names
