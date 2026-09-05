"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from typing import Any

from . import __version__
from .client import COMMANDS, PrinterClient, PrinterError
from .updates import UpdateError, install_release, latest_release, releases


COMMAND_HELP = {
    "status": "Show temperatures, position, fans, and print progress",
    "attributes": "Show printer identity and capabilities",
    "files": "List files stored on the printer",
    "start": "Start the selected print job",
    "pause": "Pause the current print",
    "stop": "Stop the current print",
    "resume": "Resume the current print",
    "web": "Show or open the printer web interface",
    "upload": "Upload a .gcode file without starting it",
    "print": "Upload a .gcode file and start printing it",
    "version": "Show the installed version and check for updates",
    "versions": "List published versions",
    "upgrade": "Install the latest or a specific published version",
}


class Style:
    """Small dependency-free terminal theme with automatic color detection."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def paint(self, text: Any, color: str) -> str:
        if not self.enabled:
            return str(text)
        return f"\033[{color}m{text}\033[0m"

    def title(self, text: Any) -> str:
        return self.paint(text, "1;36")

    def label(self, text: Any) -> str:
        return self.paint(text, "2;37")

    def good(self, text: Any) -> str:
        return self.paint(text, "1;32")

    def warn(self, text: Any) -> str:
        return self.paint(text, "1;33")

    def bad(self, text: Any) -> str:
        return self.paint(text, "1;31")


def _color_enabled(force_no_color: bool = False) -> bool:
    return not force_no_color and "NO_COLOR" not in os.environ and sys.stdout.isatty()


def build_parser() -> argparse.ArgumentParser:
    parser_options = {
        "prog": "fdm",
        "description": "Manage Elegoo network 3D printers over the local network.",
        "epilog": (
            "Examples:\n"
            "  fdm status\n"
            "  fdm --host printer.local status\n"
            "  fdm --json status | ConvertFrom-Json\n"
            "  fdm web --open"
        ),
        "formatter_class": argparse.RawDescriptionHelpFormatter,
    }
    try:
        parser = argparse.ArgumentParser(**parser_options, suggest_on_error=True)
    except TypeError:
        parser = argparse.ArgumentParser(**parser_options)
    connection = parser.add_argument_group("connection")
    connection.add_argument(
        "--host",
        default=os.getenv("FDM_HOST", "192.168.1.249"),
        help="Printer IP or hostname (env: FDM_HOST)",
    )
    connection.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FDM_PORT", "3030")),
        help="Printer websocket port (env: FDM_PORT)",
    )
    connection.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("FDM_TIMEOUT", "10")),
        help="Response timeout in seconds (env: FDM_TIMEOUT)",
    )
    output = parser.add_argument_group("output")
    output.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    output.add_argument("--compact", dest="json", action="store_true", help=argparse.SUPPRESS)
    output.add_argument("--no-color", action="store_true", help="Disable colored terminal output")
    parser.add_argument("--version", dest="show_version", action="store_true", help="Show the installed version and check for updates")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        aliases = {"attributes": ["info"], "files": ["list", "ls"]}.get(name, [])
        command = subparsers.add_parser(
            name,
            aliases=aliases,
            help=COMMAND_HELP[name],
            description=COMMAND_HELP[name],
        )
        if name == "files":
            command.add_argument("--path", default="/local", help="Printer storage path")
    web = subparsers.add_parser("web", help=COMMAND_HELP["web"], description=COMMAND_HELP["web"])
    web.add_argument("--open", action="store_true", help="Open the printer web interface in your browser")
    for name in ("upload", "print"):
        command = subparsers.add_parser(name, help=COMMAND_HELP[name], description=COMMAND_HELP[name])
        command.add_argument("file", help="Path to a .gcode file")
        if name == "print":
            command.add_argument("--yes", action="store_true", help="Skip the print confirmation prompt")
    subparsers.add_parser("version", help=COMMAND_HELP["version"], description=COMMAND_HELP["version"])
    versions_command = subparsers.add_parser("versions", help=COMMAND_HELP["versions"], description=COMMAND_HELP["versions"])
    versions_command.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    upgrade = subparsers.add_parser("upgrade", help=COMMAND_HELP["upgrade"], description=COMMAND_HELP["upgrade"])
    upgrade.add_argument("version", nargs="?", help="Release tag, such as v0.4.0; defaults to latest")
    return parser


def _value(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _print_human(command: str, response: dict[str, Any], style: Style) -> None:
    if command == "status":
        status = response.get("Status", {})
        current = _value(status, "CurrentStatus", default="unknown")
        status_names = {0: "Idle", 1: "Printing", 2: "Paused", 3: "Complete", 4: "Stopped"}
        if isinstance(current, list) and current:
            current = status_names.get(current[0], f"Code {current[0]}")
        current_text = str(current)
        current_view = style.good(current_text) if current_text in {"Idle", "Complete"} else style.warn(current_text)
        print()
        print(style.title("  PRINTER STATUS"))
        print(style.label("  +----------------+------------------------------+"))
        print(f"  | {style.label('State'):<14} | {current_view:<28} |")
        print(f"  | {style.label('Position'):<14} | {_value(status, 'CurrenCoord', 'CurrentCoord', default='unknown')!s:<28} |")
        for label, key in (("Hotbed", "TempOfHotbed"), ("Nozzle", "TempOfNozzle"), ("Enclosure", "TempOfBox")):
            temperature = _value(status, key, default="unknown")
            if isinstance(temperature, (float, int)):
                temperature = f"{temperature:.1f} C"
            print(f"  | {style.label(label):<14} | {str(temperature):<28} |")
        print(style.label("  +----------------+------------------------------+"))
        info = status.get("PrintInfo", {})
        if info.get("Filename") or info.get("Progress"):
            progress = float(info.get("Progress", 0) or 0)
            filled = min(20, max(0, round(progress / 5)))
            bar = "#" * filled + "-" * (20 - filled)
            print(f"  {style.label('Print')} {info.get('Filename') or 'unnamed'}")
            print(f"  [{style.good(bar) if progress >= 100 else bar}] {progress:.0f}%")
        print()
        return
    if command == "attributes":
        attributes = response.get("Attributes", response.get("Data", {}))
        print(style.title("  PRINTER INFORMATION"))
        for key, value in attributes.items():
            print(f"  {style.label(key + ':'):<28} {value}")
        return
    if command == "files":
        payload = response.get("Data", {}).get("Data", response.get("Data", {}))
        files = payload.get("FileList", [])
        if files:
            print(style.title(f"  FILES ({len(files)})"))
            for index, item in enumerate(files, 1):
                print(f"  {index:>3}  {item.get('name') or item.get('Name') or item}")
        else:
            print(style.warn("  No files reported by the printer."))
        return
    ack = response.get("Data", {}).get("Ack")
    if ack in (None, 0):
        print(style.good(f"  OK  {command.capitalize()} command sent successfully."))
    else:
        print(style.bad(f"  ERROR  {command.capitalize()} command returned acknowledgment {ack}."))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in raw_args and not any(item in COMMAND_HELP for item in raw_args):
        _show_version()
        return 0
    args = build_parser().parse_args(argv)
    style = Style(_color_enabled(args.no_color))
    if args.show_version:
        _show_version()
        return 0
    if args.command in {"version", "versions", "upgrade"}:
        try:
            if args.command == "upgrade":
                target = args.version or (latest_release().tag if latest_release() else None)
                if not target:
                    raise UpdateError("no published releases found")
                print(install_release(target))
                return 0
            available = releases()
            if args.command == "versions":
                if args.json:
                    print(json.dumps([{"tag": item.tag, "url": item.url} for item in available], indent=2))
                else:
                    for item in available:
                        marker = " (installed)" if item.tag.lstrip("v") == __version__ else ""
                        print(f"{item.tag}{marker}  {item.url}")
                return 0
            _show_version(available)
            return 0
        except UpdateError as exc:
            print(f"fdm: update check failed: {exc}", file=sys.stderr)
            return 1
    if args.command == "web":
        url = f"http://{args.host}/"
        if args.open:
            webbrowser.open(url)
            print(style.good(f"Opened {url}"))
        else:
            print(url)
        return 0
    if args.command in {"upload", "print"}:
        if not args.file.lower().endswith(".gcode"):
            print("fdm: error: only .gcode files can be uploaded", file=sys.stderr)
            return 1
        if not os.path.isfile(args.file):
            print(f"fdm: error: file not found: {args.file}", file=sys.stderr)
            return 1
        if args.command == "print" and not args.yes:
            answer = input(f"Start printing {args.file}? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                print(style.warn("Print cancelled."))
                return 0
        client = PrinterClient(args.host, args.port, args.timeout)
        try:
            print(style.title("Uploading") + f" {args.file}")
            client.upload(args.file, lambda progress: print(f"\r  [{('#' * round(progress * 20)).ljust(20, '-')}] {progress:.0%}", end="", flush=True))
            print()
            if args.command == "upload":
                print(style.good("  OK  Upload complete."))
                return 0
            files = client.command("files", {"Url": "/local"})
            payload = files.get("Data", {}).get("Data", files.get("Data", {}))
            remote_name = next(
                (item.get("name") for item in payload.get("FileList", []) if item.get("name", "").endswith(os.path.basename(args.file))),
                f"/local/{os.path.basename(args.file)}",
            )
            status = client.command("status")
            status_data = status.get("Status", {})
            response = client.command(
                "start",
                {
                    "Filename": remote_name,
                    "StartLayer": 0,
                    "Calibration_switch": 0,
                    "PrintPlatformType": status_data.get("PlatFormType", 0),
                    "Tlp_Switch": 0,
                    "slot_map": [],
                },
            )
            ack = response.get("Data", {}).get("Ack")
            if ack not in (None, 0):
                raise PrinterError(f"printer rejected the start command (acknowledgment {ack})")
            if args.json:
                print(json.dumps(response, indent=2))
            else:
                print(style.good(f"  OK  Print started: {remote_name}"))
            return 0
        except (PrinterError, ValueError) as exc:
            print(f"fdm: error: {exc}", file=sys.stderr)
            return 1
    command = {"info": "attributes", "list": "files", "ls": "files"}.get(args.command, args.command)
    data: dict[str, Any] = {"Url": args.path} if command == "files" else {}
    try:
        response = PrinterClient(args.host, args.port, args.timeout).command(command, data)
    except (PrinterError, ValueError) as exc:
        print(f"fdm: error: {exc}", file=sys.stderr)
        print("Tip: check the printer IP, that it is powered on, and that your computer is on the same network.", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(response, indent=2))
    else:
        _print_human(command, response, style)
    return 0


def _show_version(available: list[Any] | None = None) -> None:
    print(f"fdm {__version__}")
    try:
        release = max(available or releases(), key=lambda item: tuple(int(part) for part in item.tag.lstrip("v").split(".") if part.isdigit()))
        installed = tuple(int(part) for part in __version__.split("."))
        latest = tuple(int(part) for part in release.tag.lstrip("v").split(".") if part.isdigit())
        if latest > installed:
            print(f"Update available: {release.tag} (run: fdm upgrade)")
        else:
            print("Up to date.")
    except UpdateError:
        print("Update check unavailable.")


if __name__ == "__main__":
    raise SystemExit(main())
