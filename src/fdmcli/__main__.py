"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .client import COMMANDS, PrinterClient, PrinterError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fdm",
        description="Manage Elegoo network 3D printers over the local network.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--host", default="192.168.1.249", help="Printer IP or hostname")
    parser.add_argument("--port", type=int, default=3030, help="Printer websocket port")
    parser.add_argument("--timeout", type=float, default=10, help="Response timeout in seconds")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        command = subparsers.add_parser(name)
        if name == "files":
            command.add_argument("--path", default="/local", help="Printer storage path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data: dict[str, Any] = {"Url": args.path} if args.command == "files" else {}
    try:
        response = PrinterClient(args.host, args.port, args.timeout).command(args.command, data)
    except (PrinterError, ValueError) as exc:
        print(f"fdm: error: {exc}", file=sys.stderr)
        return 1
    separators = (",", ":") if args.compact else None
    print(json.dumps(response, indent=None if args.compact else 2, separators=separators))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
