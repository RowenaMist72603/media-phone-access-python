"""Run a small local HTTP boundary for phone signup and login."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer

from phone_access import InfraiClient, InfraiError, PhoneAccessService, PhoneCodeRequest, PhoneCodeVerification


class StreamingHandler(BaseHTTPRequestHandler):
    service = PhoneAccessService(InfraiClient.from_environment())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        try:
            if self.path == "/signup/code":
                self.service.start_signup(PhoneCodeRequest(**payload))
                self.respond(HTTPStatus.ACCEPTED, {"status": "code_sent"})
                return
            if self.path == "/login/phone":
                session = self.service.finish_login(PhoneCodeVerification(**payload))
                self.respond(HTTPStatus.OK, {"session": session})
                return
            self.respond(HTTPStatus.NOT_FOUND, {"error": "route_not_found"})
        except (InfraiError, TypeError, ValueError) as exc:
            status = exc.status if isinstance(exc, InfraiError) else HTTPStatus.BAD_REQUEST
            self.respond(status, {"error": str(exc)})

    def respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Streaming phone access listening on http://127.0.0.1:8080")
    HTTPServer(("127.0.0.1", 8080), StreamingHandler).serve_forever()
