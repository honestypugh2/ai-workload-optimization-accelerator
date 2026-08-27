# Security Policy

## Reporting a Vulnerability

This is a reference accelerator intended to be adapted inside your own
organization. It ships **no production secrets** and is designed to run locally
without Azure credentials.

If you discover a security issue in the accelerator code itself:

1. Do **not** open a public issue with exploit details.
2. Report it privately to the maintainers of the fork/repository you obtained
   this code from, following that organization's disclosure process.

## Secure Usage Guidelines

- **No secrets in config.** All example configuration under
  `workload-scenarios/**/configs/` uses placeholder values. Never commit real
  endpoints, keys, or connection strings. Use environment variables (see
  `.env.example`) or a secret store.
- **Managed identity first.** The Foundry adapters (`src/foundry/`) authenticate
  via `azure.identity.DefaultAzureCredential`. Prefer managed identity over keys
  when running in Azure.
- **Synthetic data only.** All datasets are generated synthetically
  (`src/workloads/post_call_analytics/infrastructure/synthetic.py`). Member IDs,
  transcripts, and outcomes are fabricated. Do not commit real confidential data.
- **Local-only UI.** The viewer in `apps/ui/` reads result files entirely in the
  browser and uploads nothing.

## Supported Runtime

- Python >= 3.11
- Optional Azure extras are import-guarded so the core harness runs offline.
