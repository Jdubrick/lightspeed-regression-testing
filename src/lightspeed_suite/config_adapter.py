from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


DEFAULT_TEST_MCP_SERVER_NAME = "test-mcp-server"
DEFAULT_TEST_MCP_URL = "http://test-mcp-server:8888/mcp"
TEST_MCP_PROVIDER_ID = "model-context-protocol"


class ConfigAdapterError(ValueError):
    """Raised when a Lightspeed Core config cannot be safely augmented."""


def build_test_mcp_server(
    *,
    server_name: str = DEFAULT_TEST_MCP_SERVER_NAME,
    server_url: str = DEFAULT_TEST_MCP_URL,
) -> dict[str, Any]:
    if not server_name.strip():
        raise ConfigAdapterError("Test MCP server name must be nonempty")
    if not server_url.strip():
        raise ConfigAdapterError("Test MCP server URL must be nonempty")
    return {
        "name": server_name,
        "provider_id": TEST_MCP_PROVIDER_ID,
        "url": server_url,
        "authorization_headers": {"Authorization": "client"},
    }


def _is_compatible_existing_server(
    existing: dict[str, Any], expected: dict[str, Any]
) -> bool:
    """Recognize an equivalent entry with harmless optional fields preserved."""

    for key in ("name", "provider_id", "url"):
        if existing.get(key) != expected[key]:
            return False
    return existing.get("authorization_headers") == expected["authorization_headers"]


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigAdapterError(f"Unable to read LCORE config {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigAdapterError(f"Invalid YAML in LCORE config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigAdapterError("LCORE config must contain a YAML mapping")
    return raw


def augment_lightspeed_config(
    input_path: str | Path,
    output_path: str | Path,
    *,
    server_name: str = DEFAULT_TEST_MCP_SERVER_NAME,
    server_url: str = DEFAULT_TEST_MCP_URL,
) -> Path:
    """Write an LCORE config containing the controlled test MCP server.

    The source is read-only. Existing entries and their order are preserved;
    an exact existing test entry makes the operation idempotent.
    """

    source = Path(input_path)
    destination = Path(output_path)
    try:
        if source.resolve() == destination.resolve():
            raise ConfigAdapterError("Generated LCORE config must not overwrite the source")
    except FileNotFoundError:
        # ``resolve`` can fail for a missing destination on older Python
        # versions. The destination is created below after this check.
        if source.absolute() == destination.absolute():
            raise ConfigAdapterError("Generated LCORE config must not overwrite the source")

    config = _load_yaml_mapping(source)
    raw_servers = config.get("mcp_servers", [])
    if not isinstance(raw_servers, list):
        raise ConfigAdapterError("LCORE config mcp_servers must be a list")

    servers: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, raw_server in enumerate(raw_servers):
        if not isinstance(raw_server, dict):
            raise ConfigAdapterError(f"LCORE config mcp_servers[{index}] must be a mapping")
        name = raw_server.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigAdapterError(
                f"LCORE config mcp_servers[{index}].name must be nonempty text"
            )
        if name in names:
            raise ConfigAdapterError(f"Duplicate MCP server name: {name!r}")
        names.add(name)
        servers.append(raw_server)

    test_server = build_test_mcp_server(server_name=server_name, server_url=server_url)
    if server_name in names:
        existing = next(server for server in servers if server["name"] == server_name)
        if not _is_compatible_existing_server(existing, test_server):
            raise ConfigAdapterError(
                f"MCP server {server_name!r} already exists with conflicting settings"
            )
    else:
        servers.append(test_server)

    config["mcp_servers"] = servers
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(config, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        "--lcore-config",
        required=True,
        type=Path,
        dest="input_path",
        help="Path to the source lightspeed-stack.yaml",
    )
    parser.add_argument("--output", required=True, type=Path, dest="output_path")
    parser.add_argument("--server-name", default=DEFAULT_TEST_MCP_SERVER_NAME)
    parser.add_argument("--test-mcp-url", default=DEFAULT_TEST_MCP_URL)
    args = parser.parse_args(argv)
    try:
        augment_lightspeed_config(
            args.input_path,
            args.output_path,
            server_name=args.server_name,
            server_url=args.test_mcp_url,
        )
    except ConfigAdapterError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
