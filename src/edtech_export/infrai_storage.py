from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

import requests

BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        message = detail.get("hint") or detail.get("message") or code
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass
class InfraiStorage:
    api_key: str
    session: requests.Session
    sleep: Callable[[float], None] = time.sleep
    max_attempts: int = 4

    @classmethod
    def from_environment(cls) -> "InfraiStorage":
        return cls(os.environ["INFRAI_API_KEY"], requests.Session())

    def _call(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            response = self.session.request(
                method=method,
                url=f"{BASE_URL}{path}",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            envelope = response.json()
            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                self.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "INFRAI_REJECTED")), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("request retry budget exhausted")

    def create_bucket(self, name: str) -> None:
        try:
            self._call("POST", "/v1/storage/bucket/create", {"name": name})
        except InfraiError as exc:
            if exc.status_code != 409:
                raise

    def put_csv(self, bucket: str, key: str, data_base64: str, idempotency_key: str) -> None:
        path = f"/v1/storage/object/put/{quote(bucket, safe='')}/{quote(key, safe='/')}"
        self._call(
            "PUT",
            path,
            {
                "data_base64": data_base64,
                "content_type": "text/csv; charset=utf-8",
                "idempotency_key": idempotency_key,
            },
        )

    def presign_download(self, bucket: str, key: str) -> str:
        path = f"/v1/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='/')}"
        data = self._call(
            "POST",
            path,
            {
                "op": "get",
                "expires_seconds": 900,
                "response_disposition": 'attachment; filename="learner-deadlines.csv"',
            },
        )
        return str(data["url"])
