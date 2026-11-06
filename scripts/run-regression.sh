#!/usr/bin/env bash

set -Eeuo pipefail

# Run from a release-2.1 rhdh-intelligent-assistant-configs checkout.
# The regression repository can be checked out beside it, for example:
#
#   rhdh-intelligent-assistant-configs/
#   lightspeed-regression-testing/
#
# Keep paths passed to Compose absolute where they cross the repository
# boundary.  Compose resolves relative paths from the first Compose file,
# which is the upstream file in this script.

readonly SUITE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly CONFIGS_ROOT="$(pwd -P)"
readonly BASE_COMPOSE_FILE="${CONFIGS_ROOT}/compose/compose.yaml"
readonly OKP_COMPOSE_FILE="${CONFIGS_ROOT}/compose/compose-okp.yaml"
readonly TEST_COMPOSE_FILE="${SUITE_ROOT}/compose.test.yaml"
readonly DEFAULT_VALUES_ENV="${CONFIGS_ROOT}/env/default-values.env"
readonly VALUES_ENV="${CONFIGS_ROOT}/env/values.env"
readonly LCORE_CONFIG="${CONFIGS_ROOT}/lightspeed-core-configs/lightspeed-stack.yaml"
readonly IMAGES_CONFIG="${CONFIGS_ROOT}/images.yaml"

TEMP_ROOT=""
GENERATED_LCORE_CONFIG=""
FEEDBACK_STORAGE_PATH=""
RESULTS_DIR="${RESULTS_DIR:-}"
COMPOSE_PROJECT_NAME=""
CONTAINER_ENGINE="${CONTAINER_ENGINE:-docker}"
COMPOSE_COMMAND=()
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

cleanup() {
    local status=$?
    set +e

    if [[ "$COMPOSE_STARTED" -eq 1 ]]; then
        if [[ "$status" -ne 0 ]]; then
            "${COMPOSE_COMMAND[@]}" "${COMPOSE_ARGS[@]}" logs >"${RESULTS_DIR}/compose.log" 2>&1 || true
        fi
        "${COMPOSE_COMMAND[@]}" "${COMPOSE_ARGS[@]}" down --remove-orphans >/dev/null 2>&1 || true
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

[[ "$CONFIGS_ROOT" != "$SUITE_ROOT" ]] || die "run this script from a release-2.1 rhdh-intelligent-assistant-configs checkout"

case "$CONTAINER_ENGINE" in
    docker|podman)
        COMPOSE_COMMAND=("$CONTAINER_ENGINE" compose)
        ;;
    *)
        die "unsupported CONTAINER_ENGINE '$CONTAINER_ENGINE'; expected docker or podman"
        ;;
esac

require_file "$BASE_COMPOSE_FILE"
require_file "$OKP_COMPOSE_FILE"
require_file "$LCORE_CONFIG"
require_file "$IMAGES_CONFIG"
require_file "$DEFAULT_VALUES_ENV"
require_file "$TEST_COMPOSE_FILE"

command -v "$CONTAINER_ENGINE" >/dev/null 2>&1 || die "${CONTAINER_ENGINE} is required; install it or set CONTAINER_ENGINE to docker or podman"
"${COMPOSE_COMMAND[@]}" version >/dev/null 2>&1 || die "${CONTAINER_ENGINE} compose is required"
command -v uv >/dev/null 2>&1 || die "uv is required"
command -v yq >/dev/null 2>&1 || die "yq v4 (mikefarah/yq) is required"
YQ_VERSION="$(yq --version 2>&1)" || die "unable to check yq version: ${YQ_VERSION}"
case "$YQ_VERSION" in
    "yq (https://github.com/mikefarah/yq/) version v4."*)
        ;;
    *)
        die "Mike Farah's yq v4 is required; found: ${YQ_VERSION}"
        ;;
esac

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

# Use the candidate's images.yaml, including PR edits, over env-file image defaults.
LIGHTSPEED_CORE_IMAGE="$(yq -er '."lightspeed-core".image | select(tag == "!!str")' "$IMAGES_CONFIG")" \
    || die "images.yaml must define lightspeed-core.image as text"
OKP_IMAGE="$(yq -er '.okp.image | select(tag == "!!str")' "$IMAGES_CONFIG")" \
    || die "images.yaml must define okp.image as text"
[[ -n "$LIGHTSPEED_CORE_IMAGE" && "$LIGHTSPEED_CORE_IMAGE" != *[[:space:]]* ]] \
    || die "lightspeed-core.image must be nonempty and contain no whitespace"
[[ -n "$OKP_IMAGE" && "$OKP_IMAGE" != *[[:space:]]* ]] \
    || die "okp.image must be nonempty and contain no whitespace"
export LIGHTSPEED_CORE_IMAGE OKP_IMAGE

# The adapter owns YAML changes; this runner only supplies the source and
# destination paths.  The generated file is mounted by compose.test.yaml.
(
    cd -- "$SUITE_ROOT"
    uv run python -m lightspeed_suite.config_adapter \
        --input "$LCORE_CONFIG" \
        --output "$GENERATED_LCORE_CONFIG" \
        --test-mcp-url "http://test-mcp-server:8888/mcp"
)

# Let local values.env supply Compose variables such as OKP_ACCESS_KEY.
# Exported shell values still take precedence over both files.
COMPOSE_ARGS=(
    --project-name "$COMPOSE_PROJECT_NAME"
    --env-file "$DEFAULT_VALUES_ENV"
    --env-file "$VALUES_ENV"
    -f "$BASE_COMPOSE_FILE"
    -f "$OKP_COMPOSE_FILE"
    -f "$TEST_COMPOSE_FILE"
)

# These are consumed by the test-only Compose file.  Absolute paths avoid
# Compose resolving sources relative to the upstream repository unexpectedly.
export GENERATED_LCORE_CONFIG FEEDBACK_STORAGE_PATH RESULTS_DIR

"${COMPOSE_COMMAND[@]}" "${COMPOSE_ARGS[@]}" config -q
# Fetch the selected images before starting the services.
"${COMPOSE_COMMAND[@]}" "${COMPOSE_ARGS[@]}" pull lightspeed-core okp test-mcp-server
COMPOSE_STARTED=1
"${COMPOSE_COMMAND[@]}" "${COMPOSE_ARGS[@]}" up -d --wait

(
    cd -- "$SUITE_ROOT"
    export LS_BASE_URL="${LS_BASE_URL:-http://localhost:8080}"
    export LCORE_CONFIG_PATH="$GENERATED_LCORE_CONFIG"
    export FEEDBACK_STORAGE_PATH RESULTS_DIR
    export VALIDATION_PROVIDER="vllm"

    uv run pytest -m regression "$@"
)
