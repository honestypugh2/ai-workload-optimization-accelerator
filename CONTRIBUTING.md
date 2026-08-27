# Contributing

Thanks for extending the AI Workload Optimization Accelerator. The project is
modular by design — most contributions add a new **scenario**, **optimization
strategy**, **router**, **chunker**, or **evaluator** via the registries rather
than modifying core code.

## Development setup

```bash
uv sync --extra dev
```

## Local checks (must pass before opening a PR)

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

Or use the scripts:

```bash
./scripts/lint.sh
./scripts/typecheck.sh
```

## Conventions

- **External config** uses `pydantic` models (`src/shared/configuration.py`).
- **Internal domain** uses frozen, slotted `dataclasses`.
- **Public seams** are `typing.Protocol`s in `src/shared/contracts.py`.
- New capabilities register themselves via the registries in `src/registry` and
  are activated by importing their module (see `src/cli/main.py`).
- Keep modules independently testable. Add tests under the matching
  `tests/{unit,integration,e2e}` folder.

## Data policy

- Only synthetic data. No real customer names, IDs, endpoints, or keys.
- Member-ID prefixes in examples are the generic `MBR` / `HPL` / `SVC`.

## Adding a scenario

See [REUSE_NOTES.md](REUSE_NOTES.md#adding-a-new-scenario-the-intended-path).
