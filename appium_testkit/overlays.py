"""Explicit, synchronous handlers for known overlays; no background clicks."""

from collections.abc import Callable, Iterable, Mapping

from appium_testkit.telemetry import step


class OverlayHandlers:
    def __init__(
        self,
        handlers: Mapping[str, Callable[[], bool]],
        *,
        preserved: Iterable[str] = (),
    ):
        self.handlers = dict(handlers)
        self.preserved = frozenset(preserved)

    def handle(self) -> bool:
        handled = False
        for name, handler in self.handlers.items():
            if name in self.preserved:
                continue
            with step("检查已知弹窗", overlay=name):
                handled = bool(handler()) or handled
        return handled
