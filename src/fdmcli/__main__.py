"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .client import COMMANDS, PrinterClient, PrinterError


COMMAND_HELP = {
    "status": "Show temperatures, position, fans, and print progress",
    "attributes": "Show printer identity and capabilities",
    "files": "List files stored on the printer",
    "start": "Start the selected print job",
    "pause": "Pause the current print",
    "stop": "Stop the current print",
    "resume": "Resume the current print",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fdm",
        description="Manage Elegoo network 3D printers over the local network.",
        epilog=(
            "Examples:\n"
            "  fdm status\n"
            "  fdm --host printer.local status\n"
            "  fdm --json status | ConvertFrom-Json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    connection = parser.add_argument_group("connection")
    connection.add_argument("--host", default="192.168.1.249", help="Printer IP or hostname (default: 192.168.1.249)")
    connection.add_argument("--port", type=int, default=3030, help="Printer websocket port (default: 3030)")
    connection.add_argument("--timeout", type=float, default=10, help="Response timeout in seconds (default: 10)")
    output = parser.add_argument_group("output")
    output.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    output.add_argument("--compact", dest="json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        command = subparsers.add_parser(name, help=COMMAND_HELP[name], description=COMMAND_HELP[name])
        if name == "files":
            command.add_argument("--path", default="/local", help="Printer storage path")
    return parser


def _value(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _print_human(command: str, response: dict[str, Any]) -> None:
    if command == "status":
        status = response.get("Status", {})
        current = _value(status, "CurrentStatus", default="unknown")
        status_names = {0: "Idle", 1: "Printing", 2: "Paused", 3: "Complete", 4: "Stopped"}
        if isinstance(current, list) and current:
            current = status_names.get(current[0], f"Code {current[0]}")
        print(f"Printer status: {current}")
        print(f"Position:       {_value(status, 'CurrenCoord', 'CurrentCoord', default='unknown')}")
        for label, key in (("Hotbed", "TempOfHotbed"), ("Nozzle", "TempOfNozzle"), ("Enclosure", "TempOfBox")):
            temperature = _value(status, key, default="unknown")
            if isinstance(temperature, (float, int)):
                temperature = f"{temperature:.1f} C"
            print(f"{label + ':':<16}{temperature}")
        info = status.get("PrintInfo", {})
        if info.get("Filename") or info.get("Progress"):
            print(f"Print:          {info.get('Filename') or 'unnamed'} ({info.get('Progress', 0)}%)")
        return
    if command == "attributes":
        attributes = response.get("Attributes", response.get("Data", {}))
        for key, value in attributes.items():
            print(f"{key}: {value}")
        return
    if command == "files":
        files = response.get("Data", {}).get("FileList", [])
        if files:
            for item in files:
                print(item.get("name") or item.get("Name") or item)
        else:
            print("No files reported by the printer.")
        return
    ack = response.get("Data", {}).get("Ack")
    print(f"{command.capitalize()} command sent successfully." if ack in (None, 0) else f"{command.capitalize()} command returned acknowledgment {ack}.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data: dict[str, Any] = {"Url": args.path} if args.command == "files" else {}
    try:
        response = PrinterClient(args.host, args.port, args.timeout).command(args.command, data)
    except (PrinterError, ValueError) as exc:
        print(f"fdm: error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(response, indent=2))
    else:
        _print_human(args.command, response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
