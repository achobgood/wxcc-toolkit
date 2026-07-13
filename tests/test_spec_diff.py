"""spec-diff porcelain command (Phase D — design § 12). Pure-local, no API."""
from typer.testing import CliRunner

from wxcc_flow.main import app, _spec_ops, _diff_specs

runner = CliRunner()


def _spec(ops):
    """Build a minimal OpenAPI dict from {(method, path): operationId}."""
    paths = {}
    for (method, path), op_id in ops.items():
        paths.setdefault(path, {})[method] = {"operationId": op_id}
    return {"paths": paths}


class TestSpecOps:
    def test_flattens_methods_uppercased(self):
        spec = _spec({("get", "/a"): "getA", ("post", "/a"): "postA"})
        assert set(_spec_ops(spec)) == {("GET", "/a"), ("POST", "/a")}

    def test_ignores_non_operation_keys(self):
        spec = {"paths": {"/a": {"get": {"operationId": "x"}, "parameters": []}}}
        assert set(_spec_ops(spec)) == {("GET", "/a")}

    def test_empty_spec(self):
        assert _spec_ops({}) == {}


class TestDiffSpecs:
    def test_in_sync(self):
        s = _spec({("get", "/a"): "getA"})
        assert _diff_specs(s, s) == ([], [], [])

    def test_added_and_removed(self):
        old = _spec({("get", "/a"): "getA"})
        new = _spec({("post", "/b"): "postB"})
        added, removed, changed = _diff_specs(old, new)
        assert added == [("POST", "/b")]
        assert removed == [("GET", "/a")]
        assert changed == []

    def test_changed_operation_body(self):
        old = _spec({("get", "/a"): "getA"})
        new = _spec({("get", "/a"): "getA"})
        new["paths"]["/a"]["get"]["parameters"] = [{"name": "q"}]
        added, removed, changed = _diff_specs(old, new)
        assert (added, removed) == ([], [])
        assert changed == [("GET", "/a")]


class TestSpecDiffCli:
    def test_missing_snapshot_is_clean_error(self, tmp_path):
        r = runner.invoke(app, ["spec-diff", "--snapshot", str(tmp_path / "nope.json")])
        assert r.exit_code == 1
        assert "File not found" in r.output

    def test_help_lists_exit_code_flag(self):
        r = runner.invoke(app, ["spec-diff", "--help"])
        assert r.exit_code == 0
        # Inspect the registered flags directly — robust to typer/rich help
        # rendering, which colorizes flag text and breaks substring matches on
        # newer typer/rich versions.
        import typer
        opts = {o for p in typer.main.get_command(app).commands["spec-diff"].params for o in p.opts}
        assert "--exit-code" in opts
