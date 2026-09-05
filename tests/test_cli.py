from fdmcli.__main__ import build_parser
from fdmcli.__main__ import HelpFormatter, Style, _file_page
from fdmcli.client import COMMANDS


def test_commands_have_expected_protocol_values():
    assert COMMANDS["status"] == 0
    assert COMMANDS["pause"] == 129
    assert COMMANDS["stop"] == 130


def test_parser_defaults_to_local_printer():
    args = build_parser().parse_args(["status"])
    assert args.host == "192.168.1.249"
    assert args.port == 3030
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
