"""Minimal fail-closed HTTP proxy for the v3 generated-token budget.

The proxy buffers one provider response, extracts authoritative usage, commits
the reservation, and only then returns the response to the CLI. It intentionally
supports only JSON and SSE responses from the three preregistered API shapes.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin

from agent.generation_budget_gateway import (
    BudgetExhausted,
    abort_reservation,
    commit_usage,
    reserve_request,
    seal_reservation,
)


def provider_schema(path: str) -> str:
    clean = path.split("?", 1)[0].rstrip("/")
    if clean.endswith("/responses"):
        return "openai_responses"
    if clean.endswith("/chat/completions"):
        return "openai_chat"
    if clean.endswith("/messages"):
        return "anthropic_messages"
    raise ValueError(f"unsupported provider path: {path}")


def _candidate_events(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8", errors="strict")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        payload = json.loads(text)
        return [payload] if isinstance(payload, dict) else []
    events: list[dict] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def extract_output_tokens(provider: str, raw: bytes) -> int | None:
    values: list[int] = []
    for event in _candidate_events(raw):
        candidates: list[object] = []
        usage = event.get("usage")
        if isinstance(usage, dict):
            candidates.extend([usage.get("output_tokens"), usage.get("completion_tokens")])
        response = event.get("response")
        if isinstance(response, dict) and isinstance(response.get("usage"), dict):
            rusage = response["usage"]
            candidates.extend([rusage.get("output_tokens"), rusage.get("completion_tokens")])
        message = event.get("message")
        if isinstance(message, dict) and isinstance(message.get("usage"), dict):
            musage = message["usage"]
            candidates.extend([musage.get("output_tokens"), musage.get("completion_tokens")])
        for value in candidates:
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                values.append(value)
    return max(values) if values else None


@dataclass(frozen=True)
class ProxyConfig:
    upstream_base: str
    state_path: Path
    cap: int
    timeout_seconds: float = 180.0


class BudgetProxyServer(ThreadingHTTPServer):
    config: ProxyConfig


def make_server(host: str, port: int, config: ProxyConfig) -> BudgetProxyServer:
    server = BudgetProxyServer((host, port), BudgetProxyHandler)
    server.config = config
    return server


class BudgetProxyHandler(BaseHTTPRequestHandler):
    server: BudgetProxyServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": {"message": message, "type": "budget_gateway_error"}}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            provider = provider_schema(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("request JSON must be an object")
            rewritten, reservation_id = reserve_request(
                provider=provider,
                body=body,
                state_path=self.server.config.state_path,
                cap=self.server.config.cap,
            )
        except BudgetExhausted as exc:
            self._json_error(429, str(exc))
            return
        except Exception as exc:
            self._json_error(400, f"{type(exc).__name__}: {exc}")
            return
        target = urljoin(self.server.config.upstream_base.rstrip("/") + "/", self.path.lstrip("/"))
        forwarded_headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "accept-encoding", "connection"}
        }
        request = urllib.request.Request(
            target,
            data=json.dumps(rewritten).encode("utf-8"),
            headers=forwarded_headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.server.config.timeout_seconds) as response:
                raw = response.read()
                status = response.status
                response_headers = response.headers
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            response_headers = exc.headers
            abort_reservation(
                reservation_id=reservation_id,
                state_path=self.server.config.state_path,
                cap=self.server.config.cap,
                reason=f"upstream HTTP {status}",
            )
        except Exception as exc:
            abort_reservation(
                reservation_id=reservation_id,
                state_path=self.server.config.state_path,
                cap=self.server.config.cap,
                reason=type(exc).__name__,
            )
            self._json_error(502, f"upstream failure: {type(exc).__name__}")
            return
        else:
            observed = extract_output_tokens(provider, raw)
            if observed is None:
                seal_reservation(
                    reservation_id=reservation_id,
                    state_path=self.server.config.state_path,
                    cap=self.server.config.cap,
                    reason="successful response omitted output usage",
                )
                self._json_error(502, "successful upstream response omitted authoritative output usage")
                return
            try:
                commit_usage(
                    reservation_id=reservation_id,
                    observed_output_tokens=observed,
                    state_path=self.server.config.state_path,
                    cap=self.server.config.cap,
                )
            except Exception as exc:
                self._json_error(502, f"usage commit failed: {type(exc).__name__}")
                return
        self.send_response(status)
        for key, value in response_headers.items():
            if key.lower() not in {"content-length", "transfer-encoding", "connection", "content-encoding"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--upstream-base", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--cap", type=int, required=True)
    args = parser.parse_args()
    server = make_server(
        args.host,
        args.port,
        ProxyConfig(upstream_base=args.upstream_base, state_path=args.state, cap=args.cap),
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
