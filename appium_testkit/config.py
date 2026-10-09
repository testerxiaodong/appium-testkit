"""Typed loading for device and application matrices."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml

Platform = Literal["android", "ios"]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEVICE_MATRIX = PROJECT_ROOT / "config" / "devices.yaml"
DEFAULT_APP_MATRIX = PROJECT_ROOT / "config" / "apps.yaml"


@dataclass(frozen=True, slots=True)
class DeviceSpec:
    """A physical device or simulator, independent from the app under test."""

    name: str
    platform: Platform
    udid: str
    server_url: str
    platform_version: str | None = None
    device_name: str | None = None
    system_port: int | None = None
    wda_local_port: int | None = None
    mjpeg_server_port: int | None = None
    xcode_team_id: str | None = None
    wda_bundle_id: str | None = None
    allow_provisioning_updates: bool = False
    ios_wait_for_idle_timeout: float | None = None
    command_timeout: int = 120
    no_reset: bool = True
    is_simulator: bool = False
    auto_grant_permissions: bool = False
    ios_permissions: dict[str, str] | None = None

    @property
    def lock_key(self) -> str:
        return f"{self.platform}-{self.udid}"

    @property
    def appium_host(self) -> str:
        return urlparse(self.server_url).hostname or "127.0.0.1"

    @property
    def appium_port(self) -> int:
        url = urlparse(self.server_url)
        return url.port or (443 if url.scheme == "https" else 80)

    @property
    def is_local_server(self) -> bool:
        return self.appium_host in {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True, slots=True)
class AppSpec:
    """One app's platform-specific package and application identifier."""

    name: str
    platform: Platform
    app_path: Path | None
    app_id: str
    simulator_app: Path | None = None
    device_app: Path | None = None


@dataclass(frozen=True, slots=True)
class TestTarget:
    """An app/device pair exposed to tests as the parametrized ``target``."""

    app_name: str
    app_path: Path
    app_id: str
    device: DeviceSpec

    @property
    def name(self) -> str:
        return f"{self.app_name}-{self.device.name}"

    def __getattr__(self, name: str):
        # Keep driver and lifecycle APIs concise while preserving the app/device split.
        return getattr(self.device, name)


def _read_matrix(path: Path, key: str) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Configuration file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get(key, [])
    if not isinstance(entries, list):
        raise ValueError(f"{path} must contain a '{key}' list")
    return entries


def load_devices(
    matrix_path: Path = DEFAULT_DEVICE_MATRIX,
    *,
    platform: str | None = None,
    names: set[str] | None = None,
    udid_override: str | None = None,
    server_override: str | None = None,
) -> list[DeviceSpec]:
    entries = _read_matrix(matrix_path, "devices")
    selected: list[DeviceSpec] = []
    seen_udids: set[tuple[str, str]] = set()
    seen_ports: dict[tuple[str, int], str] = {}
    for entry in entries:
        p = entry.get("platform")
        if p not in {"android", "ios"}:
            raise ValueError(f"Invalid platform for device {entry.get('name')}: {p}")
        if platform and p != platform:
            continue
        if names and entry.get("name") not in names:
            continue
        udid = (
            udid_override or entry.get("udid") or os.getenv(f"APPIUM_{p.upper()}_UDID")
        )
        if not udid:
            continue
        server = (
            server_override
            or entry.get("server_url")
            or os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
        )
        parsed = urlparse(server)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(
                f"Invalid Appium server URL for {entry.get('name')}: {server}"
            )
        ports = {
            key: entry.get(key)
            for key in ("system_port", "wda_local_port", "mjpeg_server_port")
        }
        if ports["system_port"] is None and p == "android":
            ports["system_port"] = 8200 + len(selected)
        if ports["wda_local_port"] is None and p == "ios":
            ports["wda_local_port"] = 8100 + len(selected)
        if ports["mjpeg_server_port"] is None and p == "ios":
            ports["mjpeg_server_port"] = 9100 + len(selected)
        for port in ports.values():
            if port is not None:
                key = (parsed.hostname, int(port))
                if key in seen_ports:
                    raise ValueError(
                        f"Port {port} is shared by {seen_ports[key]} and {entry.get('name')}; assign unique ports"
                    )
                seen_ports[key] = entry.get("name", udid)
        identity = (p, udid)
        if identity in seen_udids:
            raise ValueError(f"Duplicate device target: {p}/{udid}")
        seen_udids.add(identity)
        timeout = int(
            os.getenv("APPIUM_COMMAND_TIMEOUT", entry.get("command_timeout", 120))
        )
        if timeout < 1:
            raise ValueError("APPIUM_COMMAND_TIMEOUT must be greater than zero")
        for key in (
            "is_simulator",
            "no_reset",
            "auto_grant_permissions",
            "allow_provisioning_updates",
        ):
            if key in entry and not isinstance(entry[key], bool):
                raise ValueError(f"{entry.get('name')}.{key} must be a YAML boolean")
        idle = entry.get("ios_wait_for_idle_timeout")
        if idle is not None:
            import math

            if (
                p != "ios"
                or isinstance(idle, bool)
                or not isinstance(idle, (int, float))
                or not math.isfinite(idle)
                or idle < 0
            ):
                raise ValueError(
                    "ios_wait_for_idle_timeout must be a finite non-negative number for iOS"
                )
        permissions = entry.get("ios_permissions")
        if permissions is not None:
            if p != "ios" or not isinstance(permissions, dict):
                raise ValueError(
                    f"ios_permissions for {entry.get('name')} must be an iOS mapping"
                )
            invalid = {
                value
                for value in permissions.values()
                if value not in {"YES", "NO", "UNSET"}
            }
            if invalid:
                raise ValueError(
                    f"Invalid iOS permission states for {entry.get('name')}: {sorted(invalid)}"
                )
        if permissions is not None and not entry.get("is_simulator", False):
            raise ValueError(
                "ios_permissions requires an iOS simulator; remove it for real devices"
            )
        selected.append(
            DeviceSpec(
                name=entry.get("name", udid),
                platform=p,
                udid=udid,
                server_url=server.rstrip("/"),
                platform_version=entry.get("platform_version"),
                device_name=entry.get("device_name"),
                system_port=ports["system_port"],
                wda_local_port=ports["wda_local_port"],
                mjpeg_server_port=ports["mjpeg_server_port"],
                xcode_team_id=(
                    os.getenv("APPIUM_XCODE_TEAM_ID") or entry.get("xcode_team_id")
                )
                if p == "ios"
                else None,
                wda_bundle_id=entry.get("wda_bundle_id") if p == "ios" else None,
                allow_provisioning_updates=entry.get(
                    "allow_provisioning_updates", False
                ),
                ios_wait_for_idle_timeout=idle,
                command_timeout=timeout,
                no_reset=bool(entry.get("no_reset", True)),
                is_simulator=bool(entry.get("is_simulator", False)),
                auto_grant_permissions=bool(entry.get("auto_grant_permissions", False)),
                ios_permissions=permissions,
            )
        )
    return selected


def load_apps(
    matrix_path: Path = DEFAULT_APP_MATRIX,
    *,
    names: set[str] | None = None,
    platform: str | None = None,
    app_override: str | None = None,
) -> list[AppSpec]:
    """Load app profiles; app entries contain an ``android`` and/or ``ios`` mapping."""
    entries = _read_matrix(matrix_path, "apps")
    selected: list[AppSpec] = []
    for entry in entries:
        name = entry.get("name")
        if names and name not in names:
            continue
        for p in ("android", "ios"):
            if platform and p != platform:
                continue
            settings = entry.get(p)
            if not settings:
                continue
            override = app_override or os.getenv(f"APPIUM_{p.upper()}_APP")
            values = {
                "app_path": override or settings.get("app"),
                "simulator_app": None if override else settings.get("simulator_app"),
                "device_app": None if override else settings.get("device_app"),
            }
            app_id = settings.get("app_id")
            if not any(values.values()) or not app_id:
                raise ValueError(
                    f"App '{name}' requires {p}.app (or simulator_app/device_app) and {p}.app_id in {matrix_path}"
                )
            paths = {}
            for key, value in values.items():
                if value is None:
                    paths[key] = None
                else:
                    path = Path(value)
                    paths[key] = (
                        path if path.is_absolute() else PROJECT_ROOT / path
                    ).resolve()
            selected.append(AppSpec(name=name, platform=p, app_id=app_id, **paths))
    if not selected:
        raise ValueError(
            f"No app profiles configured in {matrix_path} for the selected filters"
        )
    return selected


def load_targets(
    device_matrix: Path = DEFAULT_DEVICE_MATRIX,
    app_matrix: Path = DEFAULT_APP_MATRIX,
    *,
    platform: str | None = None,
    devices: set[str] | None = None,
    apps: set[str] | None = None,
    udid_override: str | None = None,
    server_override: str | None = None,
    app_override: str | None = None,
) -> list[TestTarget]:
    if not device_matrix.is_file() and device_matrix == DEFAULT_DEVICE_MATRIX:
        device_matrix = PROJECT_ROOT / "config" / "devices.example.yaml"
    if not app_matrix.is_file() and app_matrix == DEFAULT_APP_MATRIX:
        app_matrix = PROJECT_ROOT / "config" / "apps.example.yaml"
    device_specs = load_devices(
        device_matrix,
        platform=platform,
        names=devices,
        udid_override=udid_override,
        server_override=server_override,
    )
    app_specs = load_apps(
        app_matrix, names=apps, platform=platform, app_override=app_override
    )
    targets = []
    for app in app_specs:
        for device in device_specs:
            if device.platform != app.platform:
                continue
            variant = "simulator_app" if device.is_simulator else "device_app"
            path = getattr(app, variant) or app.app_path
            if path is None:
                raise ValueError(
                    f"{app_matrix}: app '{app.name}' needs {app.platform}.{variant} "
                    f"for device '{device.name}' (or a common app path)"
                )
            targets.append(TestTarget(app.name, path, app.app_id, device))
    if not targets:
        raise ValueError(
            "No app/device combinations match. Check app and device platforms and UDIDs."
        )
    return targets
