#!/usr/bin/env bash

set -Eeuo pipefail

# This script is intended to be run from the root of a lightspeed-configs
# checkout.  The regression repository is expected to be checked out beside
# that checkout, for example:
#
#   lightspeed-configs/
#   lightspeed-regression-testing/
#
# Keep paths passed to Compose absolute where they cross the repository
# boundary.  Compose resolves relative paths from the first Compose file,
# which is the upstream file in this script.

readonly SUITE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly CONFIGS_ROOT="$(pwd -P)"
readonly BASE_COMPOSE_FILE="${CONFIGS_ROOT}/compose/compose.yaml"
readonly TEST_COMPOSE_FILE="${SUITE_ROOT}/compose.test.yaml"
readonly DEFAULT_VALUES_ENV="${CONFIGS_ROOT}/env/default-values.env"
readonly VALUES_ENV="${CONFIGS_ROOT}/env/values.env"
readonly LCORE_CONFIG="${CONFIGS_ROOT}/lightspeed-core-configs/lightspeed-stack.yaml"
readonly LLAMA_STACK_CONFIG="${CONFIGS_ROOT}/llama-stack-configs/config.yaml"
readonly RAG_CONTENT="${CONFIGS_ROOT}/rag-content"

TEMP_ROOT=""
GENERATED_LCORE_CONFIG=""
FEEDBACK_STORAGE_PATH=""
RESULTS_DIR="${RESULTS_DIR:-}"
COMPOSE_PROJECT_NAME=""
VALUES_ENV_CREATED=0
COMPOSE_STARTED=0

die() {
    printf 'run-regression: %s\n' "$*" >&2
    exit 1
}

require_file() {
    local path="$1"
    [[ -f "$path" ]] || die "required file is missing: ${path}"
}

require_directory() {
    local path="$1"
    [[ -d "$path" ]] || die "required directory is missing: ${path}"
}

cleanup() {
    local status=$?
    set +e

    if [[ "$COMPOSE_STARTED" -eq 1 ]]; then
        if [[ "$status" -ne 0 ]]; then
            docker compose "${COMPOSE_ARGS[@]}" logs >"${RESULTS_DIR}/compose.log" 2>&1 || true
        fi
        docker compose "${COMPOSE_ARGS[@]}" down --remove-orphans >/dev/null 2>&1 || true
    fi

    # Only remove the values file when this invocation created it.  A caller's
    # existing values.env is deliberately left untouched.
    if [[ "$VALUES_ENV_CREATED" -eq 1 ]]; then
        rm -f -- "$VALUES_ENV"
    fi

    if [[ -n "$TEMP_ROOT" ]]; then
        rm -rf -- "$TEMP_ROOT"
    fi

    exit "$status"
}

trap cleanup EXIT

[[ "$CONFIGS_ROOT" != "$SUITE_ROOT" ]] || die "run this script from a lightspeed-configs checkout"

require_file "$BASE_COMPOSE_FILE"
require_file "$LCORE_CONFIG"
require_file "$LLAMA_STACK_CONFIG"
require_file "$DEFAULT_VALUES_ENV"
require_directory "$RAG_CONTENT"
require_file "$TEST_COMPOSE_FILE"

command -v docker >/dev/null 2>&1 || die "docker is required"
docker compose version >/dev/null 2>&1 || die "docker compose is required"
command -v uv >/dev/null 2>&1 || die "uv is required"

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/lightspeed-regression.XXXXXX")"
GENERATED_LCORE_CONFIG="${TEMP_ROOT}/lightspeed-stack.test.yaml"
FEEDBACK_STORAGE_PATH="${TEMP_ROOT}/feedback-data"
RESULTS_DIR="${RESULTS_DIR:-${SUITE_ROOT}/results}"
if [[ "$RESULTS_DIR" != /* ]]; then
    RESULTS_DIR="${CONFIGS_ROOT}/${RESULTS_DIR}"
fi
mkdir -p -- "$FEEDBACK_STORAGE_PATH" "$RESULTS_DIR"
RESULTS_DIR="$(cd -- "$RESULTS_DIR" && pwd -P)"

# LCORE may run as a non-host user.  Match the existing local Compose
# workflow's writable feedback directory behavior for the bind mount.
chmod 777 "$FEEDBACK_STORAGE_PATH"

# Compose's project-name grammar permits lowercase letters, digits, '-' and
# '_'.  BASHPID and RANDOM are numeric, so this remains valid and unique for
# concurrent local or CI invocations.
COMPOSE_PROJECT_NAME="lightspeed-regression-${BASHPID}-${RANDOM}"
export COMPOSE_PROJECT_NAME

if [[ ! -e "$VALUES_ENV" ]]; then
    VALUES_ENV_CREATED=1
    cp -- "$DEFAULT_VALUES_ENV" "$VALUES_ENV"
fi

# The adapter owns YAML changes; this runner only supplies the source and
# destination paths.  The generated file is mounted by compose.test.yaml.
(
    cd -- "$SUITE_ROOT"
    uv run python -m lightspeed_suite.config_adapter \
        --input "$LCORE_CONFIG" \
        --output "$GENERATED_LCORE_CONFIG" \
        --test-mcp-url "http://test-mcp-server:8888/mcp"
)

COMPOSE_ARGS=(
    --project-name "$COMPOSE_PROJECT_NAME"
    --env-file "$DEFAULT_VALUES_ENV"
    -f "$BASE_COMPOSE_FILE"
    -f "$TEST_COMPOSE_FILE"
)

# These are consumed by the test-only Compose file.  Absolute paths avoid
# Compose resolving sources relative to the upstream repository unexpectedly.
export GENERATED_LCORE_CONFIG FEEDBACK_STORAGE_PATH RESULTS_DIR

docker compose "${COMPOSE_ARGS[@]}" config -q
COMPOSE_STARTED=1
docker compose "${COMPOSE_ARGS[@]}" up -d --wait

(
    cd -- "$SUITE_ROOT"
    export LS_BASE_URL="${LS_BASE_URL:-http://localhost:8080}"
    export LLAMA_STACK_CONFIG_PATH="$LLAMA_STACK_CONFIG"
    export FEEDBACK_STORAGE_PATH RESULTS_DIR
    export VALIDATION_PROVIDER="vllm"

    uv run pytest "$@"
)
