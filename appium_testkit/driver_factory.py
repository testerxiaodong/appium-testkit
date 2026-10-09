"""Platform capability construction lives at the framework boundary."""

import errno
import socket
import subprocess
import time
from urllib.parse import urlsplit

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver.webdriver import WebDriver

from appium_testkit.config import TestTarget


def build_driver_options(
    target: TestTarget, *, reinstall: bool = False, capabilities=None
):
    if not target.app_path.exists() or not (
        target.app_path.is_file() or target.app_path.is_dir()
    ):
        raise FileNotFoundError(f"App package not found: {target.app_path}")
    if target.platform == "android":
        options = UiAutomator2Options()
        caps = {
            "platformName": "Android",
            "appium:automationName": "UiAutomator2",
            "appium:app": str(target.app_path),
            "appium:appPackage": target.app_id,
            "appium:newCommandTimeout": target.command_timeout,
            "appium:noReset": target.no_reset,
        }
        caps["appium:autoGrantPermissions"] = target.auto_grant_permissions
        if target.system_port:
            caps["appium:systemPort"] = target.system_port
    else:
        options = XCUITestOptions()
        caps = {
            "platformName": "iOS",
            "appium:automationName": "XCUITest",
            "appium:app": str(target.app_path),
            "appium:bundleId": target.app_id,
            "appium:newCommandTimeout": target.command_timeout,
            "appium:noReset": target.no_reset,
        }
        if target.ios_wait_for_idle_timeout is not None:
            caps["appium:waitForIdleTimeout"] = target.ios_wait_for_idle_timeout
        if not target.is_simulator:
            caps["appium:showXcodeLog"] = True
            caps["appium:allowProvisioningDeviceRegistration"] = (
                target.allow_provisioning_updates
            )
        if target.ios_permissions:
            if not target.is_simulator:
                raise ValueError(
                    "ios_permissions can only be configured for iOS simulators"
                )
            caps["appium:permissions"] = target.ios_permissions
        if target.wda_local_port:
            caps["appium:wdaLocalPort"] = target.wda_local_port
        if target.mjpeg_server_port:
            caps["appium:mjpegServerPort"] = target.mjpeg_server_port
        if target.wda_bundle_id:
            caps["appium:updatedWDABundleId"] = target.wda_bundle_id
        if target.xcode_team_id:
            caps["appium:xcodeOrgId"] = target.xcode_team_id
            caps["appium:xcodeSigningId"] = "Apple Development"
    caps["appium:deviceName"] = target.device_name or target.udid
    caps["appium:udid"] = target.udid
    if target.platform_version:
        caps["appium:platformVersion"] = target.platform_version
    if reinstall:
        caps["appium:noReset"] = False
        caps["appium:fullReset"] = True
    caps.update(capabilities or {})
    options.load_capabilities(caps)
    return options


def _wait_for_android_port(target, port, timeout=5):
    """Check local ports before session creation can uninstall the application."""
    if not port or urlsplit(target.server_url).hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        return
    deadline = time.monotonic() + timeout
    while True:
        with socket.socket() as probe:
            # Match UiAutomator2's listener check. bind() without reuse flags
            # can fail on TIME_WAIT even though no server is listening.
            probe.settimeout(1)
            result = probe.connect_ex(("127.0.0.1", int(port)))
            if result == errno.ECONNREFUSED:
                return
            if result != 0:
                raise OSError(
                    result,
                    f"Cannot probe Android systemPort {port}; "
                    "listener status is unknown (not an occupied-port diagnosis)",
                )
        if time.monotonic() >= deadline:
            break
        time.sleep(0.25)
    details = []
    for command in (
        ["adb", "forward", "--list"],
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
    ):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            details.append(
                f"{' '.join(command)}: {result.stdout.strip() or result.stderr.strip()}"
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            details.append(f"{command[0]} unavailable: {exc}")
    raise RuntimeError(
        f"Android systemPort {port} is occupied before session creation "
        f"(device={target.udid}). Close its owning session or assign a distinct "
        "system_port to concurrently used devices. No process or forwarding was removed.\n"
        + "\n".join(details)
    )


def create_driver(
    target: TestTarget, *, reinstall: bool = False, capabilities=None
) -> WebDriver:
    options = build_driver_options(
        target, reinstall=reinstall, capabilities=capabilities
    )
    if target.platform == "android":
        _wait_for_android_port(
            target, options.to_capabilities().get("appium:systemPort")
        )
    return webdriver.Remote(
        command_executor=target.server_url,
        options=options,
    )
