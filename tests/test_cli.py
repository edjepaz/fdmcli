from fdmcli.__main__ import build_parser
from fdmcli.client import COMMANDS


def test_commands_have_expected_protocol_values():
    assert COMMANDS["status"] == 0
    assert COMMANDS["pause"] == 129
    assert COMMANDS["stop"] == 130


def test_parser_defaults_to_local_printer():
    args = build_parser().parse_args(["status"])
    assert args.host == "192.168.1.249"
    assert args.port == 3030
