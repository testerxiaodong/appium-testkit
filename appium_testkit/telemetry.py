"""Correlated, redacted event timeline; independent of pytest and app adapters."""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
from uuid import uuid4

_current = ContextVar("appium_observation", default=None)
_step_id = ContextVar("appium_step_id", default=None)
_sensitive = re.compile(
    r"password|passwd|token|secret|credential|authorization|cookie|xcodeorgid|api[_-]?key",
    re.I,
)


def redact(value):
    if isinstance(value, dict):
        return {
            str(k): "<redacted>" if _sensitive.search(str(k)) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(Bearer\s+)\S+", r"\1<redacted>", value)
        value = re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1<redacted>@", value)
        return re.sub(
            r"(?i)([\"']?(?:password|token|secret|api_key|authorization|cookie)[\"']?\s*[=:]\s*)"
            r"(?:\"[^\"]*\"|'[^']*'|[^\s&<>]+)",
            r"\1<redacted>",
            value,
        )
    return value


class Observation:
    def __init__(self, path, run_id, nodeid, target, worker="main"):
        self.path = path
        self.started = time.time()
        self.context = {
            "run_id": run_id,
            "test_id": nodeid,
            "attempt_id": uuid4().hex,
            "worker": worker,
            "device": target.name,
            "platform": target.platform,
            "app_id": target.app_id,
            "session_id": None,
        }
        self.phase = "setup"

    def emit(self, event, **fields):
        payload = redact(
            {
                **self.context,
                "timestamp": datetime.now(UTC).isoformat(),
                "phase": self.phase,
                "step_id": _step_id.get(),
                "event": event,
                **fields,
            }
        )
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            with (self.path / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(payload, ensure_ascii=False, default=str) + "\n"
                )
        except OSError:
            logging.getLogger(__name__).warning("Cannot write observation event")

    def bind(self):
        return _current.set(self)

    @staticmethod
    def unbind(token):
        _current.reset(token)


def event(event_type, **fields):
    recorder = _current.get()
    if recorder is not None:
        recorder.emit(event_type, **fields)


def traced_step(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with step(name):
                return function(*args, **kwargs)

        return wrapped

    return decorate


@contextmanager
def step(name, **fields):
    parent = _step_id.get()
    token = _step_id.set(uuid4().hex)
    start = time.monotonic()
    event("step.started", name=name, parent_step_id=parent, **fields)
    try:
        try:
            import allure

            scope = allure.step(redact(name))
        except ImportError:
            scope = nullcontext()
        with scope:
            yield
    except Exception as error:
        event(
            "step.failed",
            name=name,
            duration_ms=round((time.monotonic() - start) * 1000),
            error_type=type(error).__name__,
            error=str(error),
            **fields,
        )
        raise
    else:
        event(
            "step.passed",
            name=name,
            duration_ms=round((time.monotonic() - start) * 1000),
        )
    finally:
        _step_id.reset(token)


def observe_commands(driver, recorder):
    """Record command metadata, never command bodies, typed text or responses."""
    execute = driver.execute
    recorder.context["session_id"] = driver.session_id
    recorder.emit("session.created", capabilities=redact(driver.capabilities))

    @wraps(execute)
    def observed(command, params=None):
        start = time.monotonic()
        details = {"command": command}
        if command in {"findElement", "findElements"} and params:
            details["locator"] = {
                k: params[k] for k in ("using", "value") if k in params
            }
        try:
            result = execute(command, params)
        except Exception as error:
            recorder.emit(
                "command.failed",
                **details,
                duration_ms=round((time.monotonic() - start) * 1000),
                error_type=type(error).__name__,
                error=str(error),
            )
            raise
        recorder.emit(
            "command.completed",
            **details,
            duration_ms=round((time.monotonic() - start) * 1000),
        )
        return result

    driver.execute = observed


class PageStateError(AssertionError):
    """A visible terminal app state prevented the requested business operation."""

    def __init__(self, page, state, detail):
        self.page = page
        self.state = state
        super().__init__(f"{page}: {state}: {detail}")
