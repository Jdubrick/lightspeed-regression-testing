from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any


class ResultLogger:
    def __init__(self, results_dir: str) -> None:
        self._root = Path(results_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._run_dir = self._root / f"run_{timestamp}"
        self._run_dir.mkdir(parents=True, exist_ok=True)

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def write_case(
        self,
        test_name: str,
        provider: str | None,
        status: str,
        duration_seconds: float,
        request_data: dict[str, Any] | None = None,
        response_data: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> None:
        suffix = f"__{provider}" if provider else ""
        file_path = self._run_dir / f"{_normalize(test_name)}{suffix}.txt"
        lines = [
            "== Lightspeed Regression Test Case ==",
            f"test_name: {test_name}",
            f"provider: {provider or 'n/a'}",
            f"status: {status}",
            f"duration_seconds: {duration_seconds:.3f}",
            "",
        ]
        if notes:
            lines.extend(["notes:", notes, ""])
        if request_data is not None:
            lines.extend(["request:", json.dumps(request_data, indent=2, sort_keys=True), ""])
        if response_data is not None:
            lines.extend(
                ["response:", json.dumps(response_data, indent=2, sort_keys=True), ""]
            )

        file_path.write_text("\n".join(lines), encoding="utf-8")


def _normalize(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()

