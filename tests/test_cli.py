from fdmcli.__main__ import build_parser
from fdmcli.__main__ import Style
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
