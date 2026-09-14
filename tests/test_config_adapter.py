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
    write_config(source, {"name": "stack", "mcp_servers": [existing]})

    augment_lightspeed_config(source, output)

    generated = read_config(output)
    assert generated["mcp_servers"] == [existing, build_test_mcp_server()]
    assert read_config(source)["mcp_servers"] == [existing]


def test_adapter_is_idempotent_for_identical_entry(tmp_path: Path) -> None:
    source = tmp_path / "lightspeed-stack.yaml"
    output = tmp_path / "generated.yaml"
    write_config(source, {"mcp_servers": [build_test_mcp_server()]})

    augment_lightspeed_config(source, output)

    assert read_config(output)["mcp_servers"] == [build_test_mcp_server()]


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
