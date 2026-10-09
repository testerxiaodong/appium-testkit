"""Read-only package checks before any Appium session is created."""

import plistlib
import subprocess
import tempfile
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def supports(target, capability):
    if capability != "clear_app_data":
        raise ValueError(f"Unknown device capability: {capability}")
    return target.platform == "android" or target.is_simulator


def _run(*args):
    result = subprocess.run(args, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError(
            f"{args[0]} check failed: {result.stderr.decode(errors='replace')[-1200:]}"
        )
    return result.stdout


def validate_ios_metadata(info, target):
    expected = "iPhoneSimulator" if target.is_simulator else "iPhoneOS"
    actual = info.get("CFBundleSupportedPlatforms", [])
    if expected not in actual:
        raise ValueError(
            f"{target.name}: {target.app_path} targets {actual}; device requires {expected}. "
            "Set ios.simulator_app and ios.device_app in the app matrix."
        )
    if info.get("CFBundleIdentifier") != target.app_id:
        raise ValueError(
            f"{target.name}: bundle ID mismatch: package={info.get('CFBundleIdentifier')}, configured={target.app_id}"
        )


def validate_profile(profile, target):
    expires = profile.get("ExpirationDate")
    if not isinstance(expires, datetime) or expires.replace(tzinfo=UTC) <= datetime.now(
        UTC
    ):
        raise ValueError(
            f"{target.name}: provisioning profile is expired or missing its expiry date"
        )
    if not profile.get("ProvisionsAllDevices") and target.udid not in profile.get(
        "ProvisionedDevices", []
    ):
        raise ValueError(
            f"{target.name}: provisioning profile does not allow this device; rebuild a development/ad-hoc package"
        )
    identifier = profile.get("Entitlements", {}).get("application-identifier", "")
    pattern = identifier.partition(".")[2]
    if not pattern or not fnmatchcase(target.app_id, pattern):
        raise ValueError(
            f"{target.name}: provisioning profile application identifier does not match app_id"
        )


def validate_package(target):
    path = target.app_path
    if not path.exists():
        raise ValueError(f"{target.name}: application package does not exist: {path}")
    if target.platform == "android":
        if not path.is_file() or path.suffix.lower() != ".apk":
            raise ValueError(f"{target.name}: Android requires an APK: {path}")
        try:
            with ZipFile(path) as archive:
                if "AndroidManifest.xml" not in archive.namelist():
                    raise ValueError(
                        f"{target.name}: APK is missing AndroidManifest.xml"
                    )
        except BadZipFile as error:
            raise ValueError(f"{target.name}: invalid APK archive") from error
        return
    profile = None
    try:
        if path.is_dir() and path.suffix == ".app":
            info = plistlib.loads((path / "Info.plist").read_bytes())
            profile_path = path / "embedded.mobileprovision"
            if profile_path.exists():
                profile = profile_path.read_bytes()
        elif path.is_file() and path.suffix == ".ipa":
            with ZipFile(path) as archive:
                entries = [
                    n
                    for n in archive.namelist()
                    if n.startswith("Payload/")
                    and n.count("/") == 2
                    and n.endswith(".app/Info.plist")
                ]
                if len(entries) != 1:
                    raise ValueError("IPA must contain one Payload/*.app/Info.plist")
                info = plistlib.loads(archive.read(entries[0]))
                name = (
                    entries[0].removesuffix("Info.plist") + "embedded.mobileprovision"
                )
                if name in archive.namelist():
                    profile = archive.read(name)
        else:
            raise ValueError("iOS requires a .app directory or .ipa archive")
        validate_ios_metadata(info, target)
        if not target.is_simulator:
            if profile is None:
                raise ValueError(
                    f"{target.name}: missing embedded provisioning profile for real-device installation"
                )
            with tempfile.TemporaryDirectory(prefix="testkit-profile-") as temp:
                file = Path(temp) / "profile"
                file.write_bytes(profile)
                decoded = plistlib.loads(_run("security", "cms", "-D", "-i", str(file)))
            validate_profile(decoded, target)
            if path.is_dir():
                _run("codesign", "--verify", "--deep", "--strict", str(path))
    except (
        OSError,
        plistlib.InvalidFileException,
        BadZipFile,
        subprocess.TimeoutExpired,
    ) as error:
        raise ValueError(
            f"{target.name}: cannot inspect package {path}: {error}"
        ) from error
