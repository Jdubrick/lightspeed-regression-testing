from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lightspeed_suite.config_adapter import (
    DEFAULT_TEST_MCP_URL,
    ConfigAdapterError,
    augment_lightspeed_config,
    build_test_mcp_server,
)


def write_config(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def read_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_adapter_adds_server_and_preserves_existing_entries(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    existing = {"name": "existing", "provider_id": "model-context-protocol", "url": "http://existing"}
    original = {
        "name": "stack",
        "inference": {"providers": [{"type": "sentence_transformers"}]},
        "rag": {"okp": {"offline": True}, "retrieval": {"tool": {"sources": ["okp"]}}},
        "shields": [{"name": "lightspeed_question_validity", "config": {}}],
        "mcp_servers": [existing],
    }
    write_config(source, original)
    source_bytes = source.read_bytes()

    augment_lightspeed_config(source, output)

    generated = read_config(output)
    assert generated["mcp_servers"] == [existing, build_test_mcp_server()]
    assert generated["inference"]["providers"] == [
        {"type": "sentence_transformers"},
        {"type": "openai", "id": "openai", "api_key_env": "OPENAI_API_KEY"},
        {
            "type": "vllm",
            "id": "vllm",
            "api_key_env": "VLLM_API_KEY",
            "extra": {
                "base_url": "${env.VLLM_URL:=}",
                "max_tokens": "${env.VLLM_MAX_TOKENS:=4096}",
                "network": {"tls": {"verify": "${env.VLLM_TLS_VERIFY:=true}"}},
            },
        },
    ]
    assert generated["rag"] == original["rag"]
    assert generated["shields"] == original["shields"]
    assert source.read_bytes() == source_bytes


def test_adapter_is_idempotent_for_identical_entry(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    existing_provider = {
        "type": "openai",
        "id": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "allowed_models": ["gpt-4o-mini"],
    }
    write_config(
        source,
        {
            "inference": {"providers": [existing_provider]},
            "mcp_servers": [build_test_mcp_server()],
        },
    )

    augment_lightspeed_config(source, output)
    second_output = tmp_path / "generated-again.yaml"
    augment_lightspeed_config(output, second_output)

    assert read_config(output)["mcp_servers"] == [build_test_mcp_server()]
    assert read_config(output)["inference"]["providers"][0] == existing_provider
    assert read_config(second_output) == read_config(output)


def test_adapter_uses_default_url_when_appending(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    write_config(source, {})

    augment_lightspeed_config(source, output)

    assert read_config(output)["mcp_servers"][0]["url"] == DEFAULT_TEST_MCP_URL


@pytest.mark.parametrize(
    "servers",
    [
        ["not a mapping"],
        [{"url": "http://missing-name"}],
        [{"name": "duplicate"}, {"name": "duplicate"}],
    ],
)
def test_adapter_rejects_malformed_or_duplicate_entries(tmp_path: Path, servers: list) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    write_config(source, {"mcp_servers": servers})

    with pytest.raises(ConfigAdapterError):
        augment_lightspeed_config(source, output)


def test_adapter_rejects_non_list_mcp_servers(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    write_config(source, {"mcp_servers": {"name": "wrong type"}})

    with pytest.raises(ConfigAdapterError, match="must be a list"):
        augment_lightspeed_config(source, output)


def test_adapter_rejects_conflicting_test_server(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    conflicting = build_test_mcp_server(server_url="http://different")
    write_config(source, {"mcp_servers": [conflicting]})

    with pytest.raises(ConfigAdapterError, match="conflicting"):
        augment_lightspeed_config(source, output)


def test_adapter_rejects_test_server_without_auth_headers(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    server = build_test_mcp_server()
    server.pop("authorization_headers")
    write_config(source, {"mcp_servers": [server]})

    with pytest.raises(ConfigAdapterError, match="conflicting"):
        augment_lightspeed_config(source, output)


def test_adapter_does_not_overwrite_source(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    write_config(source, {})
    original = source.read_text(encoding="utf-8")

    with pytest.raises(ConfigAdapterError, match="must not overwrite"):
        augment_lightspeed_config(source, source)

    assert source.read_text(encoding="utf-8") == original
