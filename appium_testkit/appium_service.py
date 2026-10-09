"""Lifecycle management for an optional local Appium server."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from appium.webdriver.appium_service import AppiumService

from appium_testkit.config import TestTarget
from appium_testkit.device_lock import DEFAULT_LOCK_DIR, device_lease


def _server_is_ready(server_url: str) -> bool:
    try:
        with urllib.request.urlopen(
            f"{server_url.rstrip('/')}/status", timeout=2
        ) as response:
            return response.status == 200 and "value" in json.loads(
                response.read().decode()
            )
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


@contextmanager
def managed_appium_server(
    target: TestTarget, auto_start: bool = True, lock_dir=None, log_file=None
):
    if (
        not auto_start
        or not target.is_local_server
        or _server_is_ready(target.server_url)
    ):
        yield None
        return
    lock_dir = lock_dir or DEFAULT_LOCK_DIR
    lock_key = f"appium-server-{target.appium_host}-{target.appium_port}"
    with device_lease(lock_key, lock_dir, timeout=120):
        if _server_is_ready(target.server_url):
            yield None
            return
        service = AppiumService()
        try:
            args = ["--address", target.appium_host, "--port", str(target.appium_port)]
            if log_file is not None:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                args.extend(["--log", str(log_file), "--log-level", "info"])
            service.start(
                args=args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout_ms=30_000,
            )
            if not _server_is_ready(target.server_url):
                raise RuntimeError(
                    f"Appium did not become ready at {target.server_url}"
                )
            yield service
        except Exception as error:
            detail = ""
            if log_file is not None and Path(log_file).is_file():
                detail = " Appium log: " + str(log_file)
            raise RuntimeError(
                "Could not start local Appium. Check Appium and installed platform drivers."
                + detail
            ) from error
        finally:
            if service.is_running:
                service.stop()
