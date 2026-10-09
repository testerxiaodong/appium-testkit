"""Cross-process device lease using advisory file locks (macOS/Linux)."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows needs a platform-specific backend.
    fcntl = None

DEFAULT_LOCK_DIR = Path(tempfile.gettempdir()) / "appium-testkit" / "locks"


@contextmanager
def device_lease(lock_key: str, lock_dir: Path, timeout: float = 0):
    if fcntl is None:
        raise RuntimeError(
            "Cross-process device leases currently require POSIX fcntl (macOS/Linux)."
        )
    lock_dir.mkdir(parents=True, exist_ok=True)
    token = hashlib.sha256(lock_key.encode()).hexdigest()[:20]
    handle = (lock_dir / f"{token}.lock").open("a+")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Device {lock_key} is already leased by another pytest process."
                    ) from error
                time.sleep(min(0.25, max(0.01, deadline - time.monotonic())))
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
