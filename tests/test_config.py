from __future__ import annotations

import pytest

from lightspeed_suite.config import load_config


def _set_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALIDATION_PROVIDER", "vllm")
    monkeypatch.setenv("VALIDATION_MODEL_NAME", "validation-model")
    monkeypatch.setenv("LLAMA_STACK_CONFIG_PATH", "/configs/config.yaml")
    monkeypatch.setenv("FEEDBACK_STORAGE_PATH", "/tmp/feedback")


def test_load_config_uses_openai_for_queries_and_vllm_for_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("VALIDATION_PROVIDER", "VLLM")
    monkeypatch.setenv("OPENAI_MODEL", "query-model")

    config = load_config()

    assert config.query_config.provider == "openai"
    assert config.query_config.model == "query-model"
    assert config.validation_provider == "vllm"
    assert config.validation_model_name == "validation-model"


def test_load_config_requires_validation_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.delenv("VALIDATION_PROVIDER")

    with pytest.raises(RuntimeError, match="VALIDATION_PROVIDER"):
        load_config()


def test_load_config_rejects_non_vllm_validation_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("VALIDATION_PROVIDER", "openai")

    with pytest.raises(RuntimeError, match="must be 'vllm'"):
        load_config()
