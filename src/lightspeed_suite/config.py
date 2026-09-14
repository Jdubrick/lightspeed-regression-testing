from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class QueryConfig:
    """The single inference provider used for regression queries."""

    provider: str
    model: str


@dataclass(frozen=True)
class SuiteConfig:
    base_url: str
    openai_model: str
    validation_provider: str
    validation_model_name: str
    llama_stack_config_path: str
    user_id_prefix: str
    feedback_storage_path: str
    results_dir: str
    timeout_seconds: int
    rag_query: str
    standard_query: str
    mcp_server_name: str
    mcp_valid_auth_header: str
    mcp_invalid_auth_header: str

    @property
    def query_config(self) -> QueryConfig:
        return QueryConfig(provider="openai", model=self.openai_model)

    @property
    def mcp_valid_headers(self) -> dict[str, Any]:
        return {self.mcp_server_name: {"Authorization": self.mcp_valid_auth_header}}

    @property
    def mcp_invalid_headers(self) -> dict[str, Any]:
        return {self.mcp_server_name: {"Authorization": self.mcp_invalid_auth_header}}

    @property
    def provider_metadata(self) -> dict[str, str]:
        return {
            "query_provider": self.query_config.provider,
            "validation_provider": self.validation_provider,
            "validation_model": self.validation_model_name,
        }


def get_env(
    key: str,
    default: str | int | None = None,
    convert_to_int: bool = False,
) -> str | int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        if default is None:
            raise RuntimeError(f"Missing required environment variable: {key}")
        value: str | int = default
    else:
        value = raw.strip()

    if not convert_to_int:
        return value

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Environment variable {key} must be an integer") from exc


def load_config() -> SuiteConfig:
    """Load the fixed OpenAI-query/vLLM-validation test contract.

    Provider API credentials intentionally do not belong here. They are needed
    by LCORE, not by this client-side test process.
    """

    validation_provider = str(get_env("VALIDATION_PROVIDER")).lower()
    if validation_provider != "vllm":
        raise RuntimeError(
            "VALIDATION_PROVIDER must be 'vllm' because vLLM is the mandatory "
            f"validation provider (got {validation_provider!r})"
        )

    config = SuiteConfig(
        base_url=str(get_env("LS_BASE_URL", "http://localhost:8080")).rstrip("/"),
        openai_model=str(get_env("OPENAI_MODEL", "gpt-4o-mini")),
        validation_provider=validation_provider,
        validation_model_name=str(get_env("VALIDATION_MODEL_NAME")),
        llama_stack_config_path=str(get_env("LLAMA_STACK_CONFIG_PATH")),
        user_id_prefix=str(get_env("TEST_USER_ID_PREFIX", "test-user")),
        feedback_storage_path=str(get_env("FEEDBACK_STORAGE_PATH")),
        results_dir=str(get_env("RESULTS_DIR", "./results")),
        timeout_seconds=int(get_env("REQUEST_TIMEOUT_SECONDS", 120, convert_to_int=True)),
        rag_query=str(
            get_env(
                "RAG_QUERY",
                "How do I configure Developer Lightspeed in Red Hat Developer Hub? "
                "I am looking for the yaml snippets to assist me.",
            )
        ),
        standard_query=str(
            get_env(
                "STANDARD_QUERY",
                "Explain what Red Hat Developer Lightspeed is in one paragraph.",
            )
        ),
        mcp_server_name=str(get_env("MCP_SERVER_NAME", "test-mcp-server")),
        mcp_valid_auth_header=str(get_env("MCP_VALID_AUTH_HEADER", "test-secret-token")),
        mcp_invalid_auth_header=str(
            get_env("MCP_INVALID_AUTH_HEADER", "Bearer test-secret-token")
        ),
    )

    # Validate MCP headers encode cleanly because they are sent as JSON in one header.
    json.dumps(config.mcp_valid_headers)
    json.dumps(config.mcp_invalid_headers)
    return config
