# Lightspeed Core regression suite

This `release-2.1` branch contains the regression tests for RHDH 2.1.
It runs against a checkout of
[`redhat-developer/rhdh-intelligent-assistant-configs`](https://github.com/redhat-developer/rhdh-intelligent-assistant-configs)
on the matching `release-2.1` branch. Core 0.7 and OKP run as containers on the
same machine. Use this suite's `release-1.10` branch for RHDH 1.10.

## Test contract

All allowed test queries use OpenAI. vLLM performs mandatory question
validation before OpenAI receives a query.

The adapter creates a temporary copy of the candidate Core YAML. It adds the
OpenAI and vLLM providers needed to run the tests, plus the test MCP server.
It preserves the existing embedder and other product settings. Credentials stay
as environment variable references in the generated file.

If a required provider already exists, the adapter keeps it when its required
settings match. It stops with an error if those settings conflict. This runs
during setup, before Compose starts.

The runner forces these settings:

```text
ENABLE_VALIDATION=question_validity
VALIDATION_PROVIDER=vllm
```

The rejection test reads `config.invalid_question_response` from the shield named
`lightspeed_question_validity` in the generated Core YAML. The runner supplies
that file through `LCORE_CONFIG_PATH`, so the test follows changes to the
configured rejection text. The suite keeps its existing 15 regression cases.

## Prerequisites

- `uv`
- [Mike Farah's `yq` v4](https://github.com/mikefarah/yq) for reading `images.yaml`
- Docker with the Compose plugin (the default), or Podman with its Compose
  provider for local runs
- A matching `rhdh-intelligent-assistant-configs` checkout, including
  `compose/compose.yaml`, `compose/compose-okp.yaml`, `images.yaml`,
  `lightspeed-core-configs/lightspeed-stack.yaml` and `env/default-values.env`
- Registry authentication for the selected images using the chosen engine

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
OKP_ACCESS_KEY
```

`TEST_MCP_SERVER_IMAGE` should be an immutable tag or digest. The optional
`OPENAI_MODEL` value defaults to `gpt-4o-mini`.

Use `OKP_ACCESS_KEY` locally and in GitHub Actions. Compose passes it to the OKP
container as `ACCESS_KEY`. Setup fails if the key is missing or empty.
After supplying the other inputs:

```bash
export OKP_ACCESS_KEY='<your OKP access key>'
```

For GitHub Actions, bind the secret to the runner step's environment:

```yaml
env:
  OKP_ACCESS_KEY: ${{ secrets.OKP_ACCESS_KEY }}
```

For a local run, you can also put `OKP_ACCESS_KEY` in the configuration checkout's
ignored `env/values.env`. The runner passes both env files to Compose to resolve
variables such as `${OKP_ACCESS_KEY}`. Compose reads `env/default-values.env`
first and `env/values.env` second. Exported shell values override both files.
The `env_file` entry on the Core service only supplies Core's container; it does
not supply variables to the separate OKP service. Keep key values out of tracked
files and rendered Compose output.

Log in to the image registries before running the script. Registry credentials
are separate from the OKP content key. The planned workflow uses
`QUAY_REGISTRY_USERNAME` and `QUAY_REGISTRY_PASSWORD`, matching the existing build
workflow. Credentials must work for each image's registry. The inspected OKP
image is on `registry.redhat.io`; Core is on `quay.io`. Local users can use an
existing Docker or Podman login. Service-account support for the OKP content key
still needs investigation.

## Candidate images and Compose setup

The runner uses `yq` to read `lightspeed-core.image` and `okp.image` from
`images.yaml` in the candidate checkout, including PR changes or local edits.
Those references override image defaults in env files and previously exported
`LIGHTSPEED_CORE_IMAGE` / `OKP_IMAGE` values. The runner explicitly pulls the
selected Core, OKP and test MCP images before startup. It does not fetch image
values from another branch or use hosted OKP.

Compose files merge in this order:

1. Candidate `compose/compose.yaml`.
2. Candidate `compose/compose-okp.yaml`.
3. Suite `compose.test.yaml`.

The suite overlay mounts the generated config and writable feedback directory.
It passes provider credentials, enables validation and requires the OKP key.
Core waits for healthy OKP and for the test MCP service to start. The suite keeps
the upstream OKP URL, host-gateway mapping, embedding settings and healthchecks.
That networking setup lets both Core and host pytest use the OKP source URLs.
The 2.1 setup does not need `rag-content/`, the old Llama Stack config or
`make get-rag`.

## Run the suite

Check out the two repositories beside one another:

```text
workspace/
  rhdh-intelligent-assistant-configs/  # release-2.1
  lightspeed-regression-testing/
```

Run the script from the root of the configuration checkout:

```bash
cd rhdh-intelligent-assistant-configs
../lightspeed-regression-testing/scripts/run-regression.sh
```

For a local Podman run:

```bash
CONTAINER_ENGINE=podman \
  ../lightspeed-regression-testing/scripts/run-regression.sh
```

GitHub Actions can omit `CONTAINER_ENGINE`; Docker remains the default:

```bash
../lightspeed-regression-testing/scripts/run-regression.sh
```

The runner selects tests marked `regression`. Any arguments are forwarded to
pytest:

```bash
../lightspeed-regression-testing/scripts/run-regression.sh -k conversation -q
```

The script:

1. Validates the expected candidate files and resolves both candidate images.
2. Generates a temporary Core config with query/validation providers and test MCP.
3. Checks the merged Compose configuration without printing it, then pulls images.
4. Starts the Compose project and waits for readiness.
5. Runs the existing Python regression suite on the host, recording `results/`.
6. Collects Compose logs on failure and tears down this run's project.

The runner leaves the candidate's source config unchanged. If it creates
`env/values.env` from the committed defaults, it removes that file during cleanup.
It keeps any `values.env` that existed before the run.

## Verification without services

Syntax and whitespace checks do not require containers or credentials:

```bash
bash -n scripts/run-regression.sh
git diff --check
uv run python - <<'PY'
import ast
from pathlib import Path

import yaml

for directory in ("src", "tests"):
    for path in Path(directory).rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
yaml.safe_load(Path("compose.test.yaml").read_text(encoding="utf-8"))
PY
```

For further checks without services, you can:

- Run the existing unit tests, which use temporary YAML fixtures.
- Collect the regression cases without executing their fixtures or API requests.
- Generate a temporary Core config for review using the adapter CLI.

From the suite checkout:

```bash
uv sync --frozen
uv run pytest tests/test_config.py tests/test_config_adapter.py \
  tests/test_validation.py
uv run pytest --collect-only -m regression -q
```

For preparation only, still from the suite checkout:

```bash
review_dir="$(mktemp -d)"
uv run python -m lightspeed_suite.config_adapter \
  --input ../rhdh-intelligent-assistant-configs/lightspeed-core-configs/lightspeed-stack.yaml \
  --output "$review_dir/lightspeed-stack.test.yaml"
```

The adapter needs no credentials and does not call Compose. Review the generated
file and remove the temporary directory when finished. A live run is still needed
to verify image access, Compose startup and the regression results.
