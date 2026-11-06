from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ValidationConfigError(ValueError):
    """Raised when the active Core shield configuration is invalid."""


def _load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValidationConfigError(f"Unable to read LCORE config {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValidationConfigError(f"Invalid YAML in LCORE config {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValidationConfigError("LCORE config must contain a YAML mapping")
    return raw


def extract_validation_rejection(path: str | Path) -> str:
    """Return the configured response for an invalid question.

    The shield is selected by its stable name rather than by list position
    or its environment-backed provider_id, which Core resolves at startup.
    """

    root = _load_yaml_mapping(path)
    shields = root.get("shields")
    if not isinstance(shields, list):
        raise ValidationConfigError("LCORE config is missing shields list")

    matches = [
        item
        for item in shields
        if isinstance(item, dict)
        and item.get("name") == "lightspeed_question_validity"
    ]
    if len(matches) != 1:
        raise ValidationConfigError(
            "Expected exactly one lightspeed_question_validity shield; "
            f"found {len(matches)}"
        )

    provider_config = matches[0].get("config")
    if not isinstance(provider_config, dict):
        raise ValidationConfigError("Validation shield config must be a mapping")

    response = provider_config.get("invalid_question_response")
    if not isinstance(response, str) or not response.strip():
        raise ValidationConfigError(
            "Validation shield config.invalid_question_response must be nonempty text"
        )
    return response.strip()


def load_validation_rejection(path: str | Path) -> str:
    """Compatibility-friendly alias for extracting the configured rejection."""

    return extract_validation_rejection(path)


def normalize_response_text(value: str) -> str:
    """Normalize streamed/configured text for a stable comparison."""

    return " ".join(value.split()).casefold()
