"""Persistent named-printer configuration."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PrinterProfile:
    name: str
    host: str
    port: int = 3030
    timeout: float = 10

    def as_dict(self) -> dict[str, Any]:
        return {"host": self.host, "port": self.port, "timeout": self.timeout}


def config_path() -> Path:
    configured = os.getenv("FDM_CONFIG")
    if configured:
        return Path(configured)
    root = os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")
    return Path(root) / "fdmcli" / "config.json"


def _read() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {"default": None, "printers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read printer config {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("printers", {}), dict):
        raise RuntimeError(f"invalid printer config: {path}")
    return {"default": data.get("default"), "printers": data.get("printers", {})}


def _write(data: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="config-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def profiles() -> list[PrinterProfile]:
    data = _read()
    return [
        PrinterProfile(name, values["host"], int(values.get("port", 3030)), float(values.get("timeout", 10)))
        for name, values in sorted(data["printers"].items())
    ]


def get_profile(name: str) -> PrinterProfile:
    profile = next((item for item in profiles() if item.name == name), None)
    if profile is None:
        raise RuntimeError(f"printer profile not found: {name}")
    return profile


def default_name() -> str | None:
    return _read().get("default")


def save_profile(profile: PrinterProfile) -> None:
    data = _read()
    data["printers"][profile.name] = profile.as_dict()
    _write(data)


def remove_profile(name: str) -> None:
    data = _read()
    if name not in data["printers"]:
        raise RuntimeError(f"printer profile not found: {name}")
    del data["printers"][name]
    if data.get("default") == name:
        data["default"] = next(iter(sorted(data["printers"])), None)
    _write(data)


def set_default(name: str) -> None:
    data = _read()
    if name not in data["printers"]:
        raise RuntimeError(f"printer profile not found: {name}")
    data["default"] = name
    _write(data)
