"""Ordered app preparation with explicit validation and best-effort cleanup."""

from contextlib import contextmanager
from typing import Protocol

from appium_testkit.telemetry import step


class StateProvider(Protocol):
    def prepare(self, *, driver, target, cleanup):
        """Register compensating callbacks BEFORE mutating external state."""

    def verify(self, *, driver, target):
        """Raise if the requested application state was not established."""


class Cleanup:
    def __init__(self):
        self.callbacks = []

    def register(self, name, callback):
        self.callbacks.append((name, callback))

    def run(self):
        errors = []
        while self.callbacks:
            name, callback = self.callbacks.pop()
            try:
                with step("清理状态", operation=name):
                    callback()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("Application state cleanup failed", errors)


@contextmanager
def prepared_state(
    driver, target, *, launch="restart", provider=None, auth=None, launch_app=None
):
    if launch not in {"preserve", "restart"}:
        raise ValueError(f"Unsupported app_launch: {launch}")
    cleanup = Cleanup()
    try:
        if launch == "restart":
            with step("重启应用", app_id=target.app_id):
                if launch_app is None:
                    driver.terminate_app(target.app_id)
                    driver.activate_app(target.app_id)
                else:
                    launch_app()
        if provider is not None:
            with step("准备应用状态"):
                provider.prepare(driver=driver, target=target, cleanup=cleanup)
        if auth is not None:
            with step("建立认证状态"):
                auth()
        if provider is not None:
            with step("验证应用状态"):
                provider.verify(driver=driver, target=target)
        yield driver
    except BaseException as original:
        try:
            cleanup.run()
        except Exception as failure:
            original.add_note(str(failure))
        raise
    else:
        cleanup.run()
