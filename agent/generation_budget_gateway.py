"""Provider-agnostic core for a cumulative generated-token budget gateway.

The gateway reserves the maximum output of each request before it is sent and
rewrites the provider-specific request field to the remaining allowance. This
core is transport-independent; an HTTP forwarding layer must call ``commit``
with authoritative provider usage from the final response event.
"""
from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class BudgetExhausted(RuntimeError):
    pass


class BudgetIntegrityError(RuntimeError):
    pass


@contextmanager
def _locked(path: Path) -> Iterator[object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield stream
    finally:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _empty(cap: int) -> dict:
    return {
        "schema": "generation-budget-gateway-v1",
        "max_cumulative_output_tokens": cap,
        "committed_output_tokens": 0,
        "reservations": {},
        "completed": [],
        "violations": [],
    }


def _load(stream: object, cap: int) -> dict:
    stream.seek(0)
    raw = stream.read()
    if not raw.strip():
        return _empty(cap)
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BudgetIntegrityError("invalid gateway state JSON") from exc
    if state.get("schema") != "generation-budget-gateway-v1":
        raise BudgetIntegrityError("unexpected gateway state schema")
    if state.get("max_cumulative_output_tokens") != cap:
        raise BudgetIntegrityError("gateway cap drift")
    if not isinstance(state.get("reservations"), dict):
        raise BudgetIntegrityError("invalid reservation table")
    return state


def _save(stream: object, state: dict) -> None:
    stream.seek(0)
    stream.truncate()
    stream.write(json.dumps(state, ensure_ascii=False, indent=2))
    stream.flush()
    os.fsync(stream.fileno())


def _request_field(provider: str) -> str:
    if provider == "openai_responses":
        return "max_output_tokens"
    if provider in {"openai_chat", "anthropic_messages"}:
        return "max_tokens"
    raise ValueError(f"unsupported provider schema: {provider}")


def reserve_request(
    *, provider: str, body: dict, state_path: Path, cap: int
) -> tuple[dict, str]:
    """Reserve remaining output and return a safely rewritten request body."""
    if cap <= 0:
        raise ValueError("cap must be positive")
    field = _request_field(provider)
    requested = body.get(field)
    if requested is not None and (
        not isinstance(requested, int) or isinstance(requested, bool) or requested <= 0
    ):
        raise ValueError(f"{field} must be a positive integer when provided")
    with _locked(state_path) as stream:
        state = _load(stream, cap)
        reserved = sum(int(row["reserved_output_tokens"]) for row in state["reservations"].values())
        remaining = cap - int(state["committed_output_tokens"]) - reserved
        if remaining <= 0:
            raise BudgetExhausted("cumulative generated-token budget exhausted")
        allowance = min(requested, remaining) if requested is not None else remaining
        reservation_id = str(uuid.uuid4())
        state["reservations"][reservation_id] = {
            "provider": provider,
            "requested_output_tokens": requested,
            "reserved_output_tokens": allowance,
        }
        _save(stream, state)
    rewritten = dict(body)
    rewritten[field] = allowance
    return rewritten, reservation_id


def commit_usage(
    *, reservation_id: str, observed_output_tokens: int, state_path: Path, cap: int
) -> dict:
    if not isinstance(observed_output_tokens, int) or isinstance(observed_output_tokens, bool) or observed_output_tokens < 0:
        raise ValueError("observed_output_tokens must be a nonnegative integer")
    with _locked(state_path) as stream:
        state = _load(stream, cap)
        reservation = state["reservations"].pop(reservation_id, None)
        if reservation is None:
            raise BudgetIntegrityError("unknown or already committed reservation")
        reserved = int(reservation["reserved_output_tokens"])
        if observed_output_tokens > reserved:
            violation = {
                "reservation_id": reservation_id,
                "kind": "provider_output_exceeded_reserved_limit",
                "reserved": reserved,
                "observed": observed_output_tokens,
            }
            state["violations"].append(violation)
            _save(stream, state)
            raise BudgetIntegrityError(violation["kind"])
        state["committed_output_tokens"] += observed_output_tokens
        state["completed"].append(
            {
                "reservation_id": reservation_id,
                **reservation,
                "observed_output_tokens": observed_output_tokens,
            }
        )
        if state["committed_output_tokens"] > cap:
            state["violations"].append({"kind": "cumulative_cap_exceeded"})
            _save(stream, state)
            raise BudgetIntegrityError("cumulative cap exceeded")
        _save(stream, state)
        return state


def abort_reservation(*, reservation_id: str, state_path: Path, cap: int, reason: str) -> dict:
    with _locked(state_path) as stream:
        state = _load(stream, cap)
        reservation = state["reservations"].pop(reservation_id, None)
        if reservation is None:
            raise BudgetIntegrityError("unknown or already closed reservation")
        state.setdefault("aborted", []).append(
            {"reservation_id": reservation_id, "reason": reason, **reservation}
        )
        _save(stream, state)
        return state


def seal_reservation(*, reservation_id: str, state_path: Path, cap: int, reason: str) -> dict:
    """Fail closed when a successful provider response has no auditable usage.

    The full reserved allowance is charged so a missing usage field can never
    reset or expand the remaining budget.
    """
    with _locked(state_path) as stream:
        state = _load(stream, cap)
        reservation = state["reservations"].pop(reservation_id, None)
        if reservation is None:
            raise BudgetIntegrityError("unknown or already closed reservation")
        reserved = int(reservation["reserved_output_tokens"])
        state["committed_output_tokens"] += reserved
        state["violations"].append(
            {
                "reservation_id": reservation_id,
                "kind": "missing_authoritative_output_usage",
                "reason": reason,
                "charged_output_tokens": reserved,
            }
        )
        _save(stream, state)
        return state
