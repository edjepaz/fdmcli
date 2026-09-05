"""GitHub release discovery and self-update helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

REPOSITORY = "edjepaz/fdmcli"
RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases"


@dataclass(frozen=True)
class Release:
    tag: str
    name: str
    url: str
    assets: tuple[dict[str, Any], ...]


class UpdateError(RuntimeError):
    """Raised when release discovery or installation fails."""


def _request(url: str, timeout: float = 3) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "fdmcli"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise UpdateError(f"unable to contact GitHub: {exc}") from exc


def releases() -> list[Release]:
    data = _request(RELEASES_URL)
    return [
        Release(item["tag_name"], item.get("name") or item["tag_name"], item["html_url"], tuple(item.get("assets", [])))
        for item in data
        if not item.get("draft") and not item.get("prerelease")
    ]


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.lstrip("v").split(".") if part.isdigit())


def latest_release() -> Release | None:
    available = releases()
    return max(available, key=lambda item: version_key(item.tag), default=None)


def executable_asset(release: Release) -> dict[str, Any] | None:
    return next((asset for asset in release.assets if asset.get("name") == "fdm-windows-x64.exe"), None)


def install_release(tag: str) -> str:
    target = next((release for release in releases() if release.tag == tag or release.tag == f"v{tag.lstrip('v')}"), None)
    if target is None:
        raise UpdateError(f"release {tag} was not found")
    if getattr(sys, "frozen", False):
        asset = executable_asset(target)
        if not asset:
            raise UpdateError(f"release {target.tag} has no Windows executable asset")
        _replace_executable(asset["browser_download_url"])
        return f"updating executable to {target.tag}"
    package = f"git+https://github.com/{REPOSITORY}.git@{target.tag}"
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", package], check=True)
    return f"installed {target.tag}"


def _replace_executable(url: str) -> None:
    current = os.path.abspath(sys.executable)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as output:
        temp_path = output.name
        request = urllib.request.Request(url, headers={"User-Agent": "fdmcli"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        except (OSError, urllib.error.URLError) as exc:
            raise UpdateError(f"unable to download update: {exc}") from exc
    script = tempfile.NamedTemporaryFile("w", delete=False, suffix=".cmd")
    script.write(f'@echo off\r\n:wait\r\ntasklist /FI "PID eq {os.getpid()}" | find "{os.getpid()}" >nul && (timeout /t 1 /nobreak >nul & goto wait)\r\nmove /Y "{temp_path}" "{current}" >nul\r\nstart "" "{current}"\r\ndel "%~f0"\r\n')
    script.close()
    subprocess.Popen(["cmd", "/c", script.name], creationflags=subprocess.CREATE_NO_WINDOW)
