# Workload scenario templates

Copy this directory's structure to scaffold a new workload scenario. A scenario
is a self-contained plugin: externalized configuration + a registered
`WorkloadScenario` subclass under `src/workloads/<name>/`.

## Steps

1. Create `workload-scenarios/<your-scenario>/` mirroring `post-call-analytics/`:
   - `scenario.yaml` (validated by `shared.configuration.ScenarioConfig`)
   - `configs/pricing.example.yaml`
   - `benchmarks/*.yaml`, `evaluations/*.yaml`
   - `sample-data/dataset-profile.yaml`
2. Implement `src/workloads/<your_scenario>/scenario.py` with a
   `WorkloadScenario` subclass decorated with
   `@scenario_registry.register("<your-scenario>")`.
3. Implement synthetic data generation and any workload-specific extractors under
   `src/workloads/<your_scenario>/{domain,infrastructure}/`.
4. Import the package in `src/workloads/__init__.py` so registration runs.
5. Reuse the shared optimization strategies, routers, chunkers, and evaluators —
   only add workload-specific pieces.

Keep Azure SDK usage behind adapters and ensure the local path runs without
cloud credentials.
