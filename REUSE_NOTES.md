# Reuse Notes

This accelerator is intentionally **modular and plugin-based** so you can adopt
individual pieces without taking the whole thing. Nothing here is tied to a
specific organization, dataset, or Azure subscription.

## What is reusable, and how

| Module | Reuse as | Extension point |
| --- | --- | --- |
| `src/shared` | Domain types, protocols, config schema | Add new `dataclass`/`Protocol` contracts |
| `src/registry` | Generic `Registry[T]` + typed registries | Register your own scenarios/strategies/evaluators |
| `src/optimization` | Chunking, caching, routing, PTU sizing, token-reduction strategies | Implement `OptimizationStrategy`, `Chunker`, or a router and register it |
| `src/benchmarking` | Throughput/latency/cost harness | Point `BenchmarkConfig` at a new scenario |
| `src/evaluation` | Quality + release-gate harness | Implement `Evaluator`, add `ThresholdRule`s |
| `src/workloads` | Scenario abstraction | Subclass `WorkloadScenario`, register it |
| `src/foundry` | Model catalog + Foundry/Azure OpenAI adapters | Swap `MockModelProvider` for `FoundryModelProvider` |
| `apps/ui` | Thin local result viewer | Extend `types.ts` + components |

## Adding a new scenario (the intended path)

1. Create `src/workloads/<your_scenario>/` with a `scenario.py` that subclasses
   `WorkloadScenario` and is decorated with `@scenario_registry.register(...)`.
2. Add a `workload-scenarios/<your-scenario>/` folder with `scenario.yaml`,
   `configs/`, `benchmarks/`, `evaluations/`, and synthetic `sample-data/`.
3. Import the module in `src/cli/main.py` so registration side effects fire.
4. Run `aiwoa scenario list` to confirm it is discovered.

## Design guarantees

- **No monolith.** Each module is independently importable and unit-tested.
- **Runs offline.** Azure SDK imports are guarded; the default provider is a
  deterministic mock.
- **No organization identity.** Prefixes (`MBR`/`HPL`/`SVC`) and all data are
  synthetic and generic.
- **Registration by import.** New capabilities are discovered via registries, so
  the core never needs to know about your extensions at build time.
