# Lightspeed Core regression suite

This branch contains the Python regression contract for the RHDH 1.10 release.
It runs against a checkout of
[`redhat-ai-dev/lightspeed-configs`](https://github.com/redhat-ai-dev/lightspeed-configs)
on the matching `release-1.10` branch.

## Test contract

All allowed test queries use OpenAI. vLLM performs mandatory question
validation before OpenAI receives a query.

The runner forces these LCORE settings:

```text
ENABLE_OPENAI=true
ENABLE_VLLM=true
ENABLE_VALIDATION=true
VALIDATION_PROVIDER=vllm
```

The rejection test reads `invalid_question_response` from the active
`llama-stack-configs/config.yaml`. It therefore follows release configuration
changes without duplicating the configured response in the test suite.

## Prerequisites

- `uv`
- Docker with the Compose plugin (the default), or Podman with its Compose
  provider for local runs
- A matching `lightspeed-configs` checkout with its RAG content prepared

The runner uses Docker Compose by default. Set `CONTAINER_ENGINE=podman` to
use Podman Compose locally. `uv` uses the Python version declared in
`pyproject.toml`.

## Required runtime values

The caller must export:

```text
TEST_MCP_SERVER_IMAGE
OPENAI_API_KEY
VLLM_URL
VLLM_API_KEY
VALIDATION_MODEL_NAME
```

`TEST_MCP_SERVER_IMAGE` should be an immutable tag or digest. The optional
`OPENAI_MODEL` value defaults to `gpt-4o-mini`.

## Run the suite

Check out the two repositories beside one another:

```text
workspace/
  lightspeed-configs/
  lightspeed-regression-testing/
```

Run the script from the root of `lightspeed-configs`:

```bash
cd lightspeed-configs
../lightspeed-regression-testing/scripts/run-regression.sh
```

For a local Podman run:

```bash
CONTAINER_ENGINE=podman \
  ../lightspeed-regression-testing/scripts/run-regression.sh
```

The runner requires `rag-content/` to already exist in `lightspeed-configs`.
Prepare it with the same container engine you will use for the suite, for
example:

```bash
make get-rag CONTAINER_ENGINE=podman
```

GitHub Actions can omit `CONTAINER_ENGINE`; Docker remains the default:

```bash
../lightspeed-regression-testing/scripts/run-regression.sh
```

Any arguments are forwarded to pytest:

```bash
../lightspeed-regression-testing/scripts/run-regression.sh -k conversation -q
```

The script:

1. Validates the expected `lightspeed-configs` files and prepared RAG content.
2. Generates a temporary LCORE config containing the test MCP server.
3. Merges the upstream Compose file with `compose.test.yaml`.
4. Runs the Python suite on the host.
5. Writes structured case results under `results/` by default.
6. Collects Compose logs on failure and tears the environment down.

The source configuration in `lightspeed-configs` is never overwritten. If the
runner creates `env/values.env` from the committed defaults, it removes that
temporary file during cleanup.

## Run Python unit tests only

From this repository:

```bash
uv sync --frozen
uv run pytest tests/test_config.py tests/test_config_adapter.py \
  tests/test_validation.py
```
