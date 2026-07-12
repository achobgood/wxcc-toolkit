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
| `drift_check.py` | Parity gate: spec ⇄ generated, manifest counts, dead doc references, skip-list reconciliation. (Phase D.) |

## Regenerate

```bash
python3 -m tools.generator.generate --all --dry-run   # review the plan
python3 -m tools.generator.generate --all             # emit src/wxcc_flow/generated/
python3 -m pytest tests/test_generator.py tests/test_generator_regression.py
```

## Weekly drift runbook

_(Filled in Phase D.)_ `pull_spec.py` → `git diff specs/` → if drift: regenerate →
pytest → read-only sweep → update snapshot + commit.
