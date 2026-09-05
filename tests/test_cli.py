from fdmcli.__main__ import _connection, build_parser
from fdmcli.__main__ import HelpFormatter, Style, _file_page
from fdmcli.client import COMMANDS
from fdmcli.config import PrinterProfile, get_profile, profiles, save_profile, set_default


def test_commands_have_expected_protocol_values():
    assert COMMANDS["status"] == 0
    assert COMMANDS["pause"] == 129
    assert COMMANDS["stop"] == 130


def test_parser_defaults_to_local_printer():
    args = build_parser().parse_args(["status"])
    assert args.host is None
    assert args.printer is None
    assert args.port is None
    assert args.timeout is None
    assert not args.json


def test_parser_supports_json_output():
    args = build_parser().parse_args(["--json", "status"])
    assert args.json


def test_parser_supports_helpful_aliases():
    assert build_parser().parse_args(["info"]).command == "info"
    assert build_parser().parse_args(["ls"]).command == "ls"


def test_parser_supports_web_command():
    args = build_parser().parse_args(["web", "--open"])
    assert args.open


def test_parser_supports_upload_and_print_commands():
    assert build_parser().parse_args(["upload", "model.gcode"]).file == "model.gcode"
    args = build_parser().parse_args(["print", "model.gcode", "--yes"])
    assert args.yes


def test_parser_supports_release_commands():
    assert build_parser().parse_args(["version"]).command == "version"
    assert build_parser().parse_args(["versions"]).command == "versions"
    args = build_parser().parse_args(["upgrade", "v0.4.0"])
    assert args.version == "v0.4.0"


def test_style_is_plain_when_disabled():
    assert Style(False).good("ok") == "ok"


def test_file_listing_aliases_are_available():
    parser = build_parser()
    assert parser.parse_args(["files"]).command == "files"
    assert parser.parse_args(["list"]).command == "list"
    assert parser.parse_args(["ls"]).command == "ls"


def test_help_uses_organized_formatter():
    parser = build_parser()
    help_text = parser.format_help()
    assert "commands:" in help_text
    assert "connection:" in help_text
    assert "output:" in help_text
    assert isinstance(parser._get_formatter(), HelpFormatter)


def test_file_search_and_pagination():
    args = build_parser().parse_args(["list", "--search", "benchy", "--page", "2", "--per-page", "5"])
    assert args.search == "benchy"
    assert args.page == 2
    assert args.per_page == 5

    response = {"Data": {"Data": {"FileList": [{"name": f"benchy-{i}.gcode"} for i in range(7)]}}}
    result = _file_page(response, "BENCHY", 2, 5)
    assert result["Total"] == 7
    assert result["TotalPages"] == 2
    assert result["Files"] == [{"name": "benchy-5.gcode"}, {"name": "benchy-6.gcode"}]


def test_printer_profile_commands_parse():
    parser = build_parser()
    args = parser.parse_args(["printer", "add", "garage", "--host", "192.168.1.250"])
    assert args.printer_command == "add"
    assert args.name == "garage"
    assert args.host == "192.168.1.250"


def test_printer_profiles_persist(monkeypatch, tmp_path):
    monkeypatch.setenv("FDM_CONFIG", str(tmp_path / "config.json"))
    save_profile(PrinterProfile("home", "192.168.1.249"))
    save_profile(PrinterProfile("garage", "192.168.1.250", 3031))
    set_default("garage")
    assert [item.name for item in profiles()] == ["garage", "home"]
    assert get_profile("garage").port == 3031


def test_connection_requires_a_configured_printer(monkeypatch, tmp_path):
    monkeypatch.setenv("FDM_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.delenv("FDM_HOST", raising=False)
    args = build_parser().parse_args(["status"])
    try:
        _connection(args)
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected missing printer configuration error")
    assert "fdm printer add home --host PRINTER_IP" in message
    assert "192.168.1.249" not in message


def test_explicit_host_works_without_a_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("FDM_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.delenv("FDM_HOST", raising=False)
    args = build_parser().parse_args(["--host", "192.168.1.249", "status"])
    assert _connection(args)[:3] == ("192.168.1.249", 3030, 10)
