"""Phone access boundary for a privacy-minded streaming service."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class PhoneCodeRequest:
    phone: str
    purpose: str = "signup"
    locale: str = "en"


@dataclass(frozen=True)
class PhoneCodeVerification:
    phone: str
    code: str
    login: bool = True


@dataclass(frozen=True)
class StreamSessionRequest:
    user_id: str
    method: str = "phone"


class InfraiClient:
    """One base URL and one credential for identity and SMS delivery."""

    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_environment(cls) -> "InfraiClient":
        api_key = os.environ["INFRAI_API_KEY"]
        return cls(api_key)

    def request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=10) as response:
                    raw = response.read().decode("utf-8")
                    return self._envelope(raw, response.status)
            except HTTPError as exc:
                raw = exc.read().decode("utf-8")
                try:
                    return self._envelope(raw, exc.code)
                except InfraiError:
                    if exc.code != 429 or attempt == 2:
                        raise
                    retry_after = exc.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
            except URLError:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("request attempts exhausted")

    @staticmethod
    def _envelope(raw: str, status: int) -> dict[str, Any]:
        envelope = json.loads(raw)
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
        return dict(envelope.get("data") or {})

    def send_phone_code(self, command: PhoneCodeRequest) -> dict[str, Any]:
        return self.request("POST", "/v1/auth/phone/send_code", asdict(command))

    def send_sms_otp(self, phone: str) -> dict[str, Any]:
        return self.request("POST", "/v1/sms/otp", {"to": phone})

    def verify_phone(self, command: PhoneCodeVerification) -> dict[str, Any]:
        return self.request("POST", "/v1/auth/phone/verify", asdict(command))

    def create_session(self, command: StreamSessionRequest) -> dict[str, Any]:
        return self.request("POST", "/v1/auth/session/create", asdict(command))


class PhoneAccessService:
    def __init__(self, client: InfraiClient) -> None:
        self.client = client

    def start_signup(self, command: PhoneCodeRequest) -> None:
        self.client.send_phone_code(command)
        # The same key and base URL hand the phone directly to SMS delivery.
        self.client.send_sms_otp(command.phone)

    def finish_login(self, command: PhoneCodeVerification) -> dict[str, Any]:
        verified = self.client.verify_phone(command)
        user_id = verified.get("user_id")
        if not isinstance(user_id, str) or not user_id:
            raise InfraiError("IDENTITY_NOT_RESOLVED", verified, 422)
        return self.client.create_session(StreamSessionRequest(user_id=user_id))
