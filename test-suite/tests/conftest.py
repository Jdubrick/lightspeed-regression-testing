from __future__ import annotations

import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

import pytest

from lightspeed_suite.client import LightspeedClient
from lightspeed_suite.config import ProviderConfig, SuiteConfig, load_config
from lightspeed_suite.result_logger import ResultLogger


@dataclass
class CaseRecord:
    request_data: dict[str, Any] = field(default_factory=dict)
    response_data: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def set_request(self, payload: dict[str, Any]) -> None:
        self.request_data = payload

    def set_response(self, payload: dict[str, Any]) -> None:
        self.response_data = payload

    def add_note(self, note: str) -> None:
        self.notes = f"{self.notes}\n{note}".strip()


@pytest.fixture(scope="session")
def config() -> SuiteConfig:
    return load_config()


@pytest.fixture(scope="session")
def result_logger(config: SuiteConfig) -> ResultLogger:
    return ResultLogger(results_dir=config.results_dir)


@pytest.fixture(scope="session")
def client(config: SuiteConfig) -> Iterator[LightspeedClient]:
    instance = LightspeedClient(config.base_url, config.timeout_seconds)
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture(scope="session")
def provider_matrix(config: SuiteConfig) -> list[ProviderConfig]:
    return config.provider_matrix


@pytest.fixture(params=["openai", "vllm"])
def provider_config(request: pytest.FixtureRequest, provider_matrix: list[ProviderConfig]) -> ProviderConfig:
    provider_name = str(request.param)
    for item in provider_matrix:
        if item.provider == provider_name:
            return item
    pytest.skip(f"Provider not enabled by PROVIDER_MODE: {provider_name}")


@pytest.fixture
def user_id(config: SuiteConfig) -> str:
    return f"{config.user_id_prefix}-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def case_context(
    request: pytest.FixtureRequest, result_logger: ResultLogger
):
    @contextmanager
    def _ctx(provider: str | None = None) -> Iterator[CaseRecord]:
        started = time.perf_counter()
        record = CaseRecord()
        status = "pass"
        try:
            yield record
        except AssertionError as exc:
            status = "fail"
            record.add_note(str(exc))
            raise
        except Exception as exc:
            status = "error"
            record.add_note(f"Unexpected error: {exc}")
            record.add_note(traceback.format_exc())
            raise
        finally:
            duration = time.perf_counter() - started
            result_logger.write_case(
                test_name=request.node.name,
                provider=provider,
                status=status,
                duration_seconds=duration,
                request_data=record.request_data,
                response_data=record.response_data,
                notes=record.notes,
            )

    return _ctx

