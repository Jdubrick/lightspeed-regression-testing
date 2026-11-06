from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lightspeed_suite.validation import (
    ValidationConfigError,
    extract_validation_rejection,
    normalize_response_text,
)


def write_config(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_extracts_rejection_by_shield_name_not_position(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    rejection = """
      Please ask a software development or cloud infrastructure question.
    """
    write_config(
        path,
        {
            "shields": [
                {"name": "other", "config": {}},
                {
                    "name": "lightspeed_question_validity",
                    "provider_id": "${env.ENABLE_VALIDATION:=__disabled__}",
                    "config": {"invalid_question_response": rejection},
                },
            ]
        },
    )

    assert extract_validation_rejection(path) == rejection.strip()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"shields": {}},
        {"shields": []},
        {
            "shields": [
                {"name": "lightspeed_question_validity", "config": {}},
                {"name": "lightspeed_question_validity", "config": {}},
            ]
        },
        {
            "shields": [
                {
                    "name": "lightspeed_question_validity",
                    "config": {"invalid_question_response": "  "},
                }
            ]
        },
    ],
)
def test_rejection_extraction_rejects_invalid_shapes(tmp_path: Path, payload: dict) -> None:
    path = tmp_path / "config.yaml"
    write_config(path, payload)

    with pytest.raises(ValidationConfigError):
        extract_validation_rejection(path)


def test_normalize_response_text_collapses_whitespace_and_case() -> None:
    assert normalize_response_text("  Hello\n  THERE! ") == "hello there!"
