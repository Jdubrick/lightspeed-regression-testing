from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ValidationConfigError(ValueError):
    """Raised when the active Llama Stack validation configuration is invalid."""


def _load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValidationConfigError(f"Unable to read Llama Stack config {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValidationConfigError(f"Invalid YAML in Llama Stack config {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValidationConfigError("Llama Stack config must contain a YAML mapping")
    return raw


def extract_validation_rejection(path: str | Path) -> str:
    """Return the configured response for an invalid question.

    The provider is selected by its stable ``provider_type`` rather than by
    list position or interpolated provider id.
    """

    root = _load_yaml_mapping(path)
    providers = root.get("providers")
    if not isinstance(providers, dict):
        raise ValidationConfigError("Llama Stack config is missing providers mapping")

    safety = providers.get("safety")
    if not isinstance(safety, list):
        raise ValidationConfigError("Llama Stack config is missing providers.safety list")

    matches = [
        item
        for item in safety
        if isinstance(item, dict)
        and item.get("provider_type") == "inline::lightspeed_question_validity"
    ]
    if len(matches) != 1:
        raise ValidationConfigError(
            "Expected exactly one inline::lightspeed_question_validity provider; "
            f"found {len(matches)}"
        )

    provider_config = matches[0].get("config")
    if not isinstance(provider_config, dict):
        raise ValidationConfigError("Validation provider config must be a mapping")

    response = provider_config.get("invalid_question_response")
    if not isinstance(response, str) or not response.strip():
        raise ValidationConfigError(
            "Validation provider config.invalid_question_response must be nonempty text"
        )
    return response.strip()


def load_validation_rejection(path: str | Path) -> str:
    """Compatibility-friendly alias for extracting the configured rejection."""

    return extract_validation_rejection(path)


def normalize_response_text(value: str) -> str:
    """Normalize streamed/configured text for a stable comparison."""

    return " ".join(value.split()).casefold()
