# Lightspeed Regression Testing Hub

## Sync Upstream Configs

This repository mirrors selected upstream configuration files from
[github.com/redhat-ai-dev/lightspeed-configs](https://github.com/redhat-ai-dev/lightspeed-configs/tree/main) for regression testing. Run the sync script
to overwrite local copies with the exact upstream versions:

```bash
./scripts/sync.sh
```

The sync process updates these tracked files:

- `compose/llama-stack-configs/config.yaml`
- `compose/lightspeed-core-configs/lightspeed-stack.yaml`
- `compose/lightspeed-core-configs/rhdh-profile.py`
- `compose/env/default-values.env`

The script intentionally overwrites those files every run.

## Environment Secrets

`compose/env/default-values.env` is the committed template synced from upstream.
Create your own local `values.env` for secret or environment-specific values.

```bash
cp compose/env/default-values.env compose/env/values.env
```

## Lightspeed API Regression Test Suite

### Provider Modes

Use `PROVIDER_MODE` to choose which inference providers run:

- `both` (default)
- `openai_only`
- `vllm_only`

Example run:
```
PROVIDER_MODE=vllm_only pytest test-suite/tests -q
```

### Test Environment Variables

`FEEDBACK_STORAGE_PATH` behavior depends on how you run the suite:

- `lightspeed-core` now writes feedback to a host bind mount at `./feedback-data`
  (mounted into the container at `/tmp/data/feedback`).
- Direct local pytest run: set `FEEDBACK_STORAGE_PATH=./feedback-data`
- `make compose-up` prepares `./feedback-data` with writable permissions for the container.

Optional overrides:

- `LS_BASE_URL` (default `http://localhost:8080`)
- `OPENAI_MODEL` (default `gpt-4o-mini`)
- `VLLM_MODEL` (default `redhataillama-31-8b-instruct`) --> team cluster
- `RESULTS_DIR` (default `./results` locally; compose test container sets `/results`)

### Run Commands

Build test image:

```bash
make test-suite-build
```

Run tests in compose:

```bash
make test-suite-run
```

Logs are written as structured `.txt` case files under `results/run_<timestamp>/`.

Example local run (outside container):

```bash
mkdir -p ./compose/feedback-data results
FEEDBACK_STORAGE_PATH=./compose/feedback-data PROVIDER_MODE=vllm_only pytest test-suite/tests -q
```
