"""Drift gate (Phase D — design § 12). Pure-local, no API calls."""
import json

from tools.generator import drift_check as D


class TestNormPath:
    def test_params_collapse(self):
        assert D.norm_path("/{orgId}/project/{projectId}/flows/{flowId}") == \
            "/{}/project/{}/flows/{}"

    def test_emitted_placeholders_match_spec(self):
        emitted = D.norm_path("/{c.org_id}/project/{c.project_id}/v2/flows/{flow_id}")
        spec = D.norm_path("/{orgId}/project/{projectId}/v2/flows/{flowId}")
        assert emitted == spec


class TestPartition:
    """Pins the live coverage math (overrides YAML header comment)."""

    def setup_method(self):
        self.spec_ops = D.load_spec_ops()
        self.ov = D.load_overrides()
        self.classes, self.errors = D.classify_spec_ops(self.spec_ops, self.ov)

    def test_no_classification_errors(self):
        assert self.errors == []

    def test_91_ops_partition(self):
        assert len(self.spec_ops) == 91
        assert len(self.classes["generated"]) == 55
        assert len(self.classes["blocked"]) == 1
        assert len(self.classes["skip_endpoint"]) == 22
        assert len(self.classes["skip_tag"]) == 13

    def test_manifest_counts(self):
        manifest = json.loads(D.MANIFEST_PATH.read_text())
        assert len(manifest) == 58
        assert len({r["operationId"] for r in manifest}) == 56
        assert sum(1 for r in manifest if r.get("extra")) == 2
        assert sum(1 for r in manifest if r.get("top_level")) == 57

    def test_keep_endpoints_excuses_8_hand_survivors(self):
        keep = self.ov["keep_endpoints"]
        assert len(keep) == 8
        assert set(keep) == {"configure", "set-project", "init", "template",
                             "events", "connectors", "schema", "spec-diff"}


class TestReferenceScanner:
    def test_code_spans_yields_fenced_and_inline_only(self):
        text = ("prose wxcc-flow bogus\n"
                "`wxcc-flow list`\n"
                "```bash\n"
                "# comment wxcc-flow ignored\n"
                "wxcc-flow get FLOW_ID\n"
                "```\n")
        spans = [s for _, s in D.code_spans(text)]
        assert spans == ["wxcc-flow list", "wxcc-flow get FLOW_ID"]

    def test_token_ignores_flags_and_placeholders(self):
        m = D._TOKEN.search("wxcc-flow list --type SUBFLOW")
        assert (m.group(1), m.group(2)) == ("list", None)
        assert D._TOKEN.search("wxcc-flow <command>") is None
        assert D._TOKEN.search("wxcc-flow ACTIVITY") is None

    def test_token_captures_api_triples(self):
        m = D._TOKEN.search("wxcc-flow api flows-v2 validate FILE")
        assert (m.group(1), m.group(2), m.group(3)) == ("api", "flows-v2", "validate")


class TestGateGreen:
    """The full drift gate passes — the Phase D end state."""

    def test_all_checks_clean(self):
        results = D.run_checks()
        problems = {k: v for k, v in results.items() if k != "counts" and v}
        assert problems == {}
