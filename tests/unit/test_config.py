"""Device and app matrix parsing tests; these do not require Appium or devices."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from appium_testkit.config import load_apps, load_devices, load_targets


def write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("platform", "expected_ports"),
    [
        ("android", (8200, None, None)),
        ("ios", (None, 8100, 9100)),
    ],
)
def test_device_matrix_filters_platform_and_assigns_default_ports(
    tmp_path, platform, expected_ports
):
    matrix = write_yaml(
        tmp_path / "devices.yaml",
        {
            "devices": [
                {
                    "name": "pixel",
                    "platform": "android",
                    "udid": "emulator-5554",
                    "server_url": "http://127.0.0.1:4723",
                    "is_simulator": True,
                },
                {
                    "name": "iphone",
                    "platform": "ios",
                    "udid": "SIMULATOR-UDID",
                    "server_url": "http://127.0.0.1:4723",
                    "is_simulator": True,
                },
            ]
        },
    )

    devices = load_devices(matrix, platform=platform)

    assert len(devices) == 1
    assert devices[0].platform == platform
    assert (
        devices[0].system_port,
        devices[0].wda_local_port,
        devices[0].mjpeg_server_port,
    ) == expected_ports


def test_device_matrix_ignores_entries_without_udid(tmp_path):
    matrix = write_yaml(
        tmp_path / "devices.yaml",
        {
            "devices": [
                {
                    "name": "unconfigured",
                    "platform": "android",
                    "server_url": "http://127.0.0.1:4723",
                }
            ]
        },
    )

    assert load_devices(matrix) == []


def test_device_matrix_rejects_duplicate_udids(tmp_path):
    entry = {
        "platform": "android",
        "udid": "emulator-5554",
        "server_url": "http://127.0.0.1:4723",
    }
    matrix = write_yaml(
        tmp_path / "devices.yaml",
        {"devices": [{**entry, "name": "one"}, {**entry, "name": "two"}]},
    )

    with pytest.raises(ValueError, match="Duplicate device target"):
        load_devices(matrix)


def test_device_matrix_rejects_shared_parallel_driver_ports(tmp_path):
    matrix = write_yaml(
        tmp_path / "devices.yaml",
        {
            "devices": [
                {
                    "name": name,
                    "platform": "android",
                    "udid": udid,
                    "server_url": "http://127.0.0.1:4723",
                    "system_port": 8200,
                }
                for name, udid in (("one", "emulator-1"), ("two", "emulator-2"))
            ]
        },
    )

    with pytest.raises(ValueError, match="Port 8200 is shared"):
        load_devices(matrix)


def test_device_matrix_rejects_invalid_server_urls(tmp_path):
    matrix = write_yaml(
        tmp_path / "devices.yaml",
        {
            "devices": [
                {
                    "name": "android",
                    "platform": "android",
                    "udid": "emulator-5554",
                    "server_url": "not-a-url",
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="Invalid Appium server URL"):
        load_devices(matrix)


def test_device_matrix_rejects_invalid_ios_permission_states(tmp_path):
    matrix = write_yaml(
        tmp_path / "devices.yaml",
        {
            "devices": [
                {
                    "name": "iphone",
                    "platform": "ios",
                    "udid": "SIMULATOR-UDID",
                    "server_url": "http://127.0.0.1:4723",
                    "ios_permissions": {"camera": "ALLOW"},
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="Invalid iOS permission states"):
        load_devices(matrix)


def test_app_matrix_filters_platform_and_resolves_relative_paths(tmp_path):
    matrix = write_yaml(
        tmp_path / "apps.yaml",
        {
            "apps": [
                {
                    "name": "sample",
                    "android": {"app": "test-apps/sample.apk", "app_id": "app.sample"},
                    "ios": {"app": "test-apps/Sample.app", "app_id": "app.sample.ios"},
                }
            ]
        },
    )

    apps = load_apps(matrix, names={"sample"}, platform="android")

    assert len(apps) == 1
    assert apps[0].platform == "android"
    assert apps[0].app_path.is_absolute()
    assert apps[0].app_path.name == "sample.apk"


def test_target_matrix_pairs_only_compatible_app_and_device_platforms(tmp_path):
    devices = write_yaml(
        tmp_path / "devices.yaml",
        {
            "devices": [
                {
                    "name": "android",
                    "platform": "android",
                    "udid": "emulator-5554",
                    "server_url": "http://127.0.0.1:4723",
                },
                {
                    "name": "ios",
                    "platform": "ios",
                    "udid": "SIMULATOR-UDID",
                    "server_url": "http://127.0.0.1:4723",
                },
            ]
        },
    )
    apps = write_yaml(
        tmp_path / "apps.yaml",
        {
            "apps": [
                {
                    "name": "sample",
                    "android": {"app": "sample.apk", "app_id": "app.sample"},
                    "ios": {"app": "Sample.app", "app_id": "app.sample.ios"},
                }
            ]
        },
    )

    targets = load_targets(devices, apps)

    assert [(target.platform, target.device.name) for target in targets] == [
        ("android", "android"),
        ("ios", "ios"),
    ]


def test_target_matrix_rejects_no_compatible_app_device_pair(tmp_path):
    devices = write_yaml(
        tmp_path / "devices.yaml",
        {
            "devices": [
                {
                    "name": "android",
                    "platform": "android",
                    "udid": "emulator-5554",
                    "server_url": "http://127.0.0.1:4723",
                }
            ]
        },
    )
    apps = write_yaml(
        tmp_path / "apps.yaml",
        {
            "apps": [
                {
                    "name": "sample",
                    "ios": {"app": "Sample.app", "app_id": "app.sample.ios"},
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="No app/device combinations match"):
        load_targets(devices, apps)
