"""Per-test log context and failure artifact collection."""

from __future__ import annotations

import json
import logging
import plistlib
import re
import subprocess
from collections import deque
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from appium_testkit.telemetry import redact


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")[:180] or "test"


def test_artifact_dir(root: Path, run_id: str, nodeid: str, target) -> Path:
    path = (
        root
        / safe_name(run_id)
        / safe_name(target.name)
        / (safe_name(nodeid) + "-" + uuid4().hex[:8])
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _redact(value):
    return redact(value)


def redact_xml(source):
    """Preserve valid XML while masking credentials and secure input nodes."""
    root = ElementTree.fromstring(source)
    for node in root.iter():
        secure = node.get("password") == "true" or "SecureTextField" in node.get(
            "type", ""
        )
        for key, value in list(node.attrib.items()):
            if secure and key in {"text", "label", "value", "name", "content-desc"}:
                node.set(key, "<redacted>")
            elif key == "password" and value in {"true", "false"}:
                continue
            else:
                node.set(key, str(redact({key: value})[key]))
        if node.text:
            node.text = redact(node.text)
    return ElementTree.tostring(root, encoding="unicode")


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def application_metadata(target):
    """Best-effort installed build identity. Never guess a missing app version."""
    try:
        if target.platform == "android":
            result = subprocess.run(
                [
                    "adb",
                    "-s",
                    target.udid,
                    "shell",
                    "dumpsys",
                    "package",
                    target.app_id,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            values = {}
            for key in ("versionName", "versionCode"):
                match = re.search(rf"\b{key}=([^\s]+)", result.stdout)
                values[key] = match.group(1) if match else None
            return values
        if target.is_simulator:
            container = subprocess.run(
                [
                    "xcrun",
                    "simctl",
                    "get_app_container",
                    target.udid,
                    target.app_id,
                    "app",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            ).stdout.strip()
            with (Path(container) / "Info.plist").open("rb") as stream:
                info = plistlib.load(stream)
            return {
                key: info.get(key)
                for key in ("CFBundleShortVersionString", "CFBundleVersion")
            }
        return {
            "unavailable": "Real-device build identity requires device-farm/app metadata"
        }
    except Exception as error:
        return {"unavailable": str(error)}


def configure_logging(path: Path, run_id: str, nodeid: str, target) -> logging.Handler:
    logger = logging.getLogger("appium_testkit")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(path / "test.log", encoding="utf-8")
    handler.setFormatter(
        RedactingFormatter(
            "%(asctime)s %(levelname)s %(name)s run="
            + run_id
            + " device="
            + target.name
            + " test="
            + safe_name(nodeid)
            + " %(message)s"
        )
    )
    logger.addHandler(handler)
    return handler


def capture_failure(
    driver, path: Path, target=None, *, system_logs=True, started=None, server_log=None
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    errors = {}
    actions = {}
    if driver is not None:
        actions = {
            "screenshot.png": lambda: driver.save_screenshot(
                str(path / "screenshot.png")
            ),
            "page-source.xml": lambda: (path / "page-source.xml").write_text(
                redact_xml(driver.page_source), encoding="utf-8"
            ),
            "capabilities.json": lambda: (path / "capabilities.json").write_text(
                json.dumps(_redact(driver.capabilities), indent=2, default=str),
                encoding="utf-8",
            ),
        }
    else:
        errors["driver"] = "Session unavailable; failure may precede session creation"
    for filename, action in actions.items():
        try:
            if action() is False:
                raise OSError("Artifact command returned false")
        except Exception as error:  # An artifact error must not hide the test failure.
            errors[filename] = str(error)
    if system_logs and target is not None and target.platform == "android":
        try:
            result = subprocess.run(
                ["adb", "-s", target.udid, "logcat", "-d", "-t", "3000"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode:
                raise OSError(result.stderr or f"adb exited {result.returncode}")
            # The device clock can differ from the host; preserve the bounded
            # device buffer rather than incorrectly filtering by host time.
            (path / "logcat.txt").write_text(redact(result.stdout), encoding="utf-8")
            app_lines = [
                line
                for line in result.stdout.splitlines()
                if "flutter" in line or target.app_id in line
            ]
            (path / "app-log-excerpt.txt").write_text(
                redact("\n".join(app_lines)), encoding="utf-8"
            )
        except Exception as error:
            errors["logcat.txt"] = str(error)
    if system_logs and target is not None and target.platform == "ios":
        try:
            if target.is_simulator:
                container = subprocess.run(
                    [
                        "xcrun",
                        "simctl",
                        "get_app_container",
                        target.udid,
                        target.app_id,
                        "app",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                ).stdout.strip()
                with (Path(container) / "Info.plist").open("rb") as stream:
                    executable = plistlib.load(stream)["CFBundleExecutable"]
                predicate = f"process == {json.dumps(executable)}"
                result = subprocess.run(
                    [
                        "xcrun",
                        "simctl",
                        "spawn",
                        target.udid,
                        "log",
                        "show",
                        "--style",
                        "compact",
                        "--last",
                        "2m",
                        "--predicate",
                        predicate,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True,
                )
                content = result.stdout
            elif driver is not None:
                content = json.dumps(driver.get_log("syslog"), default=str)
            else:
                raise RuntimeError(
                    "Real-device syslog requires an active supported driver"
                )
            (path / "ios-system.log").write_text(
                redact(content[-500_000:]), encoding="utf-8"
            )
        except Exception as error:
            errors["ios-system.log"] = str(error)
    if system_logs:
        if server_log and Path(server_log).is_file():
            try:
                with Path(server_log).open(errors="replace") as stream:
                    lines = deque(stream, maxlen=2000)
                session_id = getattr(driver, "session_id", None)
                matching = [
                    line for line in lines if not session_id or session_id[:8] in line
                ]
                (path / "appium-server-excerpt.log").write_text(
                    redact("".join(matching)), encoding="utf-8"
                )
            except Exception as error:
                errors["appium-server-excerpt.log"] = str(error)
        else:
            errors["appium-server-excerpt.log"] = (
                "No local server log; server may be external or reused"
            )
    (path / "manifest.json").write_text(
        json.dumps(
            redact(
                {
                    "captured_at": datetime.now().astimezone().isoformat(),
                    "test_started_epoch": started,
                    "system_log_scope": "bounded device buffer; may include earlier app sessions",
                    "available": [p.name for p in path.iterdir() if p.is_file()],
                    "unavailable": errors,
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def attach_evidence(path, phase):
    try:
        import allure
    except ImportError:
        return
    types = {
        ".png": allure.attachment_type.PNG,
        ".xml": allure.attachment_type.XML,
        ".json": allure.attachment_type.JSON,
    }
    for artifact in sorted(path.iterdir()):
        if artifact.is_file():
            try:
                allure.attach.file(
                    str(artifact),
                    name=f"{phase}/{artifact.name}",
                    attachment_type=types.get(
                        artifact.suffix, allure.attachment_type.TEXT
                    ),
                )
            except Exception:
                logging.getLogger(__name__).warning("Cannot attach %s", artifact.name)
