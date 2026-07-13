# wxcc-flow command generator

Generates `wxcc-flow api <group> <op>` commands (and, once promoted, top-level
commands) from the committed Flow Store OpenAPI snapshot. Forked from the
`/webexCalling` OpenAPI→typer generator, retargeted to the `wxcc_flow`
`FlowClient`/`config`/`output` seams and stripped to a single spec.

See `docs/plans/2026-07-12-generator-fork-design.md` for the design contract.

## Files

| File | Role |
|------|------|
| `parser.py` | Spec walk → `Endpoint` dataclasses (skip/block/warn resolution, dedup, typed scalars, allOf-merged request bodies). |
| `renderer.py` | `Endpoint` → typer command source (spec-literal paths, multipart, pagination loops, blocked stubs, warn banners, feature keys). |
| `generate.py` | Orchestrator: load spec + overrides → lint → per-group emission → wholesale registry + manifest rewrite. `--dry-run` prints the plan. |
| `flow-store-overrides.yaml` | Every deviation from the spec (groups, skips, blocks, warns, multipart, param names, pagination, table columns, feature keys). NEVER hand-edit emitted files — change this instead. |
| `pull_spec.py` | `GET {base}/v3/api-docs` → `specs/flow-store-api-docs.json` (refresh the snapshot). |
| `drift_check.py` | Parity gate (report-only; `--enforce` exits 1): artifacts git-tracked, spec ⇄ manifest partition, emitted-source URLs, root command surface, documented counts, dead `wxcc-flow` doc references. |

## Regenerate

```bash
uv run python -m tools.generator.generate --all --dry-run   # review the plan
uv run python -m tools.generator.generate --all             # emit src/wxcc_flow/generated/
uv run pytest -q
```

(`uv run` installs the `dev` dependency group — pytest + PyYAML — automatically.)

## Weekly drift runbook

1. **Check for drift** — `uv run wxcc-flow spec-diff --exit-code`
   (live `/v3/api-docs` vs `specs/flow-store-api-docs.json`). Exit 0 / "In
   sync." → done for the week.
2. **Refresh the snapshot** — `uv run python -m tools.generator.pull_spec`,
   then review `git diff specs/` to see exactly what changed.
3. **Review the plan** — `uv run python -m tools.generator.generate --all
   --dry-run`. New or changed operations usually need an overrides decision
   first (skip/block/warn, `command_names` entry, `top_level_commands`
   promotion) in `flow-store-overrides.yaml`.
4. **Regenerate** — `uv run python -m tools.generator.generate --all`.
5. **Test** — `uv run pytest -q` (pure-local, no API cost). If the op counts
   legitimately changed, update the pinned partition numbers in
   `tests/test_drift_check.py` AND the coverage-math comment at the top of
   `flow-store-overrides.yaml`.
6. **Gate** — `uv run python tools/generator/drift_check.py --enforce`
   (artifacts tracked, spec⇄manifest parity, emitted URLs, root surface,
   documented counts, dead doc references).
7. **Golden spot-check** — run a few read-only commands live (`list`,
   `global-vars`, `versions FLOW_ID`) and compare shapes against
   `docs/plans/eval/goldens/`. Caveat: goldens can be ERROR captures — read
   the golden before treating it as a shape reference.
8. **Commit** — snapshot + overrides + emitted files + docs in ONE commit so
   the gate stays green at every revision.

### Debugging recipe: a list command prints `[]`

A 200 is NOT success — the server may wrap the array in an envelope the
renderer doesn't know. Re-run with `--debug` and read the response body: if it
is `{"variables": [...]}`-shaped, add a `response_list_keys` entry
(`<operationId>: <envelope key>`) to `flow-store-overrides.yaml` and
regenerate. Precedent: `getGlobalVariables: variables` (found live in Phase C).
