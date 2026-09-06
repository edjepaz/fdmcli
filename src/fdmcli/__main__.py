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
from .config import PrinterProfile, config_path, default_name, get_profile, profiles, remove_profile, save_profile, set_default
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
    "printer": "Add, edit, remove, select, and list printer profiles",
}
COMMAND_EPILOG = {
    "status": "Use --json for scripts. The status response includes temperatures, motion, fans, and print progress.",
    "attributes": "The info alias is equivalent to attributes.",
    "files": (
        "Files are returned in pages of 20 by default. Use --search for a case-insensitive filename filter "
        "and --page-size to change the page size."
    ),
    "start": "The printer must already have a print file selected. Use print to upload a local G-code file first.",
    "pause": "Pausing affects the active print on the selected printer.",
    "resume": "Resuming affects the paused print on the selected printer.",
    "stop": "Stopping affects the active print on the selected printer and may not be reversible.",
    "web": "Without --open, this prints the printer web address. With --open, it opens that address in your browser.",
    "upload": "Only sliced .gcode files are accepted. Uploading does not start a print.",
    "print": (
        "Only sliced .gcode files are accepted. This uploads the file and starts a real print; "
        "use --yes for unattended operation."
    ),
    "version": "This checks GitHub for a newer stable release after printing the installed version.",
    "versions": "Use --json for a machine-readable list of stable releases.",
    "upgrade": "Without a version, the latest stable release is installed. Pass a tag to install an exact release.",
}
DEFAULT_PAGE_SIZE = 20


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


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keep help columns readable in narrow and wide terminals."""

    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=32, width=100)


def build_parser() -> argparse.ArgumentParser:
    parser_options = {
        "prog": "fdm",
        "description": "Manage Elegoo network 3D printers over the local network.",
        "epilog": (
            "Examples:\n"
            "  fdm status\n"
            "  fdm --host printer.local status\n"
            "  fdm --json status | ConvertFrom-Json\n"
            "  fdm web --open\n\n"
            "Printer selection:\n"
            "  --host overrides --printer, saved profiles, and FDM_HOST.\n"
            "  --printer selects a saved profile; otherwise the saved default is used.\n"
            "  --port and --timeout override the selected profile.\n"
            "  Configure a profile with: fdm printer add home --host PRINTER_IP\n\n"
            "Environment:\n"
            "  FDM_HOST, FDM_PORT, and FDM_TIMEOUT provide connection defaults.\n"
            "  FDM_CONFIG changes the profile file location.\n"
            "  NO_COLOR disables terminal colors."
        ),
        "formatter_class": HelpFormatter,
    }
    try:
        parser = argparse.ArgumentParser(**parser_options, suggest_on_error=True)
    except TypeError:
        parser = argparse.ArgumentParser(**parser_options)
    connection = parser.add_argument_group("connection")
    connection.add_argument(
        "--host",
        default=None,
        help="Printer IP or hostname; overrides --printer and profile settings",
    )
    connection.add_argument(
        "--port",
        type=int,
        default=None,
        help="Printer websocket port; overrides profile settings",
    )
    connection.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Response timeout in seconds; overrides profile settings",
    )
    connection.add_argument("--printer", metavar="NAME", help="Named printer profile to use")
    output = parser.add_argument_group("output")
    output.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    output.add_argument("--compact", dest="json", action="store_true", help=argparse.SUPPRESS)
    output.add_argument("--no-color", action="store_true", help="Disable colored terminal output")
    parser.add_argument("--version", dest="show_version", action="store_true", help="Show the installed version and check for updates")
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="commands",
        metavar="COMMAND",
    )
    for name in COMMANDS:
        aliases = {"attributes": ["info"], "files": ["list", "ls"]}.get(name, [])
        command = subparsers.add_parser(
            name,
            aliases=aliases,
            help=COMMAND_HELP[name],
            description=COMMAND_HELP[name],
            epilog=COMMAND_EPILOG.get(name),
            formatter_class=HelpFormatter,
        )
        if name == "files":
            command.add_argument("--path", default="/local", metavar="PATH", help="Printer storage path (default: /local)")
            command.add_argument("--search", "-s", metavar="TEXT", help="Filter filenames by this text (case-insensitive)")
            command.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
            command.add_argument(
                "--per-page",
                "--page-size",
                dest="per_page",
                type=int,
                default=DEFAULT_PAGE_SIZE,
                help=f"Files per page (default: {DEFAULT_PAGE_SIZE})",
            )
    web = subparsers.add_parser(
        "web",
        help=COMMAND_HELP["web"],
        description=COMMAND_HELP["web"],
        epilog=COMMAND_EPILOG["web"],
        formatter_class=HelpFormatter,
    )
    web.add_argument("--open", action="store_true", help="Open the printer web interface in your browser")
    for name in ("upload", "print"):
        command = subparsers.add_parser(
            name,
            help=COMMAND_HELP[name],
            description=COMMAND_HELP[name],
            epilog=COMMAND_EPILOG[name],
            formatter_class=HelpFormatter,
        )
        command.add_argument("file", metavar="FILE", help="Path to a .gcode file")
        if name == "print":
            command.add_argument("--yes", action="store_true", help="Skip the print confirmation prompt")
    subparsers.add_parser(
        "version",
        help=COMMAND_HELP["version"],
        description=COMMAND_HELP["version"],
        epilog=COMMAND_EPILOG["version"],
        formatter_class=HelpFormatter,
    )
    versions_command = subparsers.add_parser(
        "versions",
        help=COMMAND_HELP["versions"],
        description=COMMAND_HELP["versions"],
        epilog=COMMAND_EPILOG["versions"],
        formatter_class=HelpFormatter,
    )
    versions_command.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    upgrade = subparsers.add_parser(
        "upgrade",
        help=COMMAND_HELP["upgrade"],
        description=COMMAND_HELP["upgrade"],
        epilog=COMMAND_EPILOG["upgrade"],
        formatter_class=HelpFormatter,
    )
    upgrade.add_argument("version", nargs="?", metavar="VERSION", help="Release tag, such as v0.4.0; defaults to latest")
    printer = subparsers.add_parser(
        "printer",
        aliases=["printers"],
        help=COMMAND_HELP["printer"],
        description=COMMAND_HELP["printer"],
        epilog=(
            "Profiles are stored in the path shown by 'fdm printer list'.\n"
            "The first added profile becomes the default. Use 'fdm printer use NAME' to change it.\n"
            "Use --printer NAME on any printer command to target a profile for one operation."
        ),
        formatter_class=HelpFormatter,
    )
    printer_subparsers = printer.add_subparsers(dest="printer_command", required=True, title="actions", metavar="ACTION")
    printer_subparsers.add_parser(
        "list",
        help="List saved printer profiles",
        description="List saved printer profiles and identify the default with '*'.",
        epilog="Use --json before the command to export the profile list for scripts: fdm --json printer list.",
        formatter_class=HelpFormatter,
    )
    add = printer_subparsers.add_parser(
        "add",
        help="Add a named printer profile",
        description="Save a printer connection for reuse by later commands.",
        formatter_class=HelpFormatter,
    )
    add.add_argument("name", metavar="NAME", help="Profile name, such as home")
    add.add_argument("--host", required=True, metavar="HOST", help="Printer IP address or hostname")
    add.add_argument("--port", type=int, default=3030, metavar="PORT", help="Websocket port (default: 3030)")
    add.add_argument("--timeout", type=float, default=10, metavar="SECONDS", help="Response timeout (default: 10)")
    edit = printer_subparsers.add_parser(
        "edit",
        help="Edit a saved printer profile",
        description="Change only the connection settings provided; omitted values are preserved.",
        formatter_class=HelpFormatter,
    )
    edit.add_argument("name", metavar="NAME", help="Existing profile name")
    edit.add_argument("--host", metavar="HOST", help="New printer IP address or hostname")
    edit.add_argument("--port", type=int, metavar="PORT", help="New websocket port")
    edit.add_argument("--timeout", type=float, metavar="SECONDS", help="New response timeout")
    remove = printer_subparsers.add_parser(
        "remove",
        help="Remove a saved printer profile",
        description="Delete a saved profile. This asks for confirmation unless --yes is supplied.",
        formatter_class=HelpFormatter,
    )
    remove.add_argument("name", metavar="NAME", help="Existing profile name")
    remove.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    use = printer_subparsers.add_parser(
        "use",
        help="Set the default printer profile",
        description="Select the profile used when --host and --printer are not provided.",
        formatter_class=HelpFormatter,
    )
    use.add_argument("name", metavar="NAME", help="Existing profile name")
    return parser


def _value(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _connection(args: argparse.Namespace) -> tuple[str, int, float, str | None]:
    saved = profiles()
    configured_default = default_name()
    if args.printer:
        selected = get_profile(args.printer)
    elif configured_default:
        selected = get_profile(configured_default)
    elif len(saved) == 1:
        selected = saved[0]
    else:
        selected = None
    host = args.host or (selected.host if selected else os.getenv("FDM_HOST"))
    if not host:
        raise RuntimeError(
            "No printer is configured.\n\n"
            f"Add a printer with:\n  fdm printer add home --host PRINTER_IP\n\n"
            f"Saved profiles are stored in: {config_path()}"
        )
    port = args.port or (selected.port if selected else int(os.getenv("FDM_PORT", "3030")))
    timeout = args.timeout or (selected.timeout if selected else float(os.getenv("FDM_TIMEOUT", "10")))
    return host, port, timeout, selected.name if selected else None


def _print_profiles(style: Style, as_json: bool) -> None:
    saved = profiles()
    default = default_name()
    if as_json:
        print(json.dumps({
            "config": str(config_path()),
            "default": default,
            "printers": [{"name": item.name, **item.as_dict()} for item in saved],
        }, indent=2))
        return
    print(style.title("  PRINTER PROFILES"))
    print(style.label(f"  Config: {config_path()}"))
    if not saved:
        print(style.warn("  No saved printer profiles."))
        return
    for item in saved:
        marker = style.good("*") if item.name == default else " "
        print(f"  {marker} {item.name:<18} {item.host}:{item.port}  timeout={item.timeout:g}s")


def _handle_printer_command(args: argparse.Namespace, style: Style) -> int:
    action = args.printer_command
    try:
        if action == "list":
            _print_profiles(style, args.json)
        elif action == "add":
            save_profile(PrinterProfile(args.name, args.host, args.port, args.timeout))
            print(style.good(f"  Added printer profile '{args.name}'."))
        elif action == "edit":
            current = get_profile(args.name)
            save_profile(PrinterProfile(
                args.name,
                args.host or current.host,
                args.port or current.port,
                args.timeout or current.timeout,
            ))
            print(style.good(f"  Updated printer profile '{args.name}'."))
        elif action == "remove":
            if not args.yes and input(f"Remove printer profile '{args.name}'? [y/N] ").strip().lower() not in {"y", "yes"}:
                print(style.warn("  Removal cancelled."))
                return 0
            remove_profile(args.name)
            print(style.good(f"  Removed printer profile '{args.name}'."))
        elif action == "use":
            set_default(args.name)
            print(style.good(f"  Default printer is now '{args.name}'."))
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"fdm: error: {exc}", file=sys.stderr)
        return 1


def _file_page(response: dict[str, Any], search: str | None, page: int, per_page: int) -> dict[str, Any]:
    payload = response.get("Data", {}).get("Data", response.get("Data", {}))
    all_files = payload.get("FileList", [])
    if search:
        needle = search.casefold()
        all_files = [
            item for item in all_files
            if needle in str(item.get("name") or item.get("Name") or item).casefold()
        ]
    total = len(all_files)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    return {
        "Files": all_files[start:start + per_page],
        "Page": page,
        "PerPage": per_page,
        "Total": total,
        "TotalPages": total_pages,
        "Search": search or "",
    }


def _print_human(command: str, response: dict[str, Any], style: Style, file_page: dict[str, Any] | None = None) -> None:
    if command == "status":
        status = response.get("Status", {})
        current = _value(status, "CurrentStatus", default="unknown")
        status_names = {0: "Idle", 1: "Printing", 2: "Paused", 3: "Complete", 4: "Stopped"}
        if isinstance(current, list) and current:
            current = status_names.get(current[0], f"Code {current[0]}")
        current_text = str(current)
        current_view = style.good(current_text) if current_text in {"Idle", "Complete"} else style.warn(current_text)

        def row(label: str, value: Any, value_style: str | None = None) -> str:
            label_cell = style.label(f"{label:<14}")
            value_text = f"{str(value):<28}"
            if value_style == "good":
                value_cell = style.good(value_text)
            elif value_style == "warn":
                value_cell = style.warn(value_text)
            else:
                value_cell = value_text
            return f"  | {label_cell} | {value_cell} |"

        print()
        print(style.title("  PRINTER STATUS"))
        print(style.label("  +----------------+------------------------------+"))
        print(row("State", current_text, "good" if current_text in {"Idle", "Complete"} else "warn"))
        print(row("Position", _value(status, "CurrenCoord", "CurrentCoord", default="unknown")))
        for label, key in (("Hotbed", "TempOfHotbed"), ("Nozzle", "TempOfNozzle"), ("Enclosure", "TempOfBox")):
            temperature = _value(status, key, default="unknown")
            if isinstance(temperature, (float, int)):
                temperature = f"{temperature:.1f} C"
            print(row(label, temperature))
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
            label = f"{key}:"
            print(f"  {style.label(f'{label:<26}')} {value}")
        return
    if command == "files":
        file_page = file_page or _file_page(response, None, 1, DEFAULT_PAGE_SIZE)
        files = file_page["Files"]
        if files:
            search_label = f" matching {file_page['Search']!r}" if file_page["Search"] else ""
            print(style.title(f"  FILES ({file_page['Total']}{search_label})"))
            first = (file_page["Page"] - 1) * file_page["PerPage"]
            for index, item in enumerate(files, first + 1):
                print(f"  {index:>3}  {item.get('name') or item.get('Name') or item}")
            print(
                style.label(
                    f"  Page {file_page['Page']} of {file_page['TotalPages']} "
                    f"({len(files)} shown)"
                )
            )
        else:
            message = f"No files match {file_page['Search']!r}." if file_page["Search"] else "No files reported by the printer."
            print(style.warn(f"  {message}"))
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
    if args.command in {"printer", "printers"}:
        return _handle_printer_command(args, style)
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
    try:
        host, port, timeout, selected_profile = _connection(args)
    except RuntimeError as exc:
        print(f"fdm: error: {exc}", file=sys.stderr)
        return 1
    if args.command == "web":
        url = f"http://{host}/"
        if args.open:
            webbrowser.open(url)
            print(style.good(f"Opened {url}"))
        else:
            print(url)
        return 0
    if args.command in {"files", "list", "ls"}:
        if args.page < 1:
            print("fdm: error: --page must be at least 1", file=sys.stderr)
            return 2
        if args.per_page < 1:
            print("fdm: error: --per-page must be at least 1", file=sys.stderr)
            return 2
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
        client = PrinterClient(host, port, timeout)
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
        response = PrinterClient(host, port, timeout).command(command, data)
    except (PrinterError, ValueError) as exc:
        print(f"fdm: error: {exc}", file=sys.stderr)
        print("Tip: check the printer IP, that it is powered on, and that your computer is on the same network.", file=sys.stderr)
        return 1
    if args.json:
        if command == "files":
            print(json.dumps(_file_page(response, args.search, args.page, args.per_page), indent=2))
        else:
            print(json.dumps(response, indent=2))
    else:
        file_page = _file_page(response, args.search, args.page, args.per_page) if command == "files" else None
        _print_human(command, response, style, file_page)
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
