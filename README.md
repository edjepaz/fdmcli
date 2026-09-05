# fdmcli

`fdmcli` is a friendly command-line client for Elegoo network 3D printers that expose the local SDCP websocket protocol. It has been tested with the Elegoo Centauri Carbon.

## Install

```powershell
py -m pip install git+https://github.com/edjepaz/fdmcli.git
```

For development:

```powershell
py -m pip install -e ".[test]"
```

## Usage

```powershell
fdm status
fdm attributes
fdm files
fdm pause
fdm resume
fdm stop
```

The default host is `192.168.1.249`, so the shortest command is `fdm status`. Override it with `--host` when using another printer:

```powershell
fdm --host printer.local status
```

Human-readable output is the default. Use `--json` for scripts:

```powershell
fdm --json status | ConvertFrom-Json
fdm --json --host printer.local status > status.json
```

Run `fdm --help` or `fdm status --help` for built-in guidance. The older `--compact` flag remains accepted as an alias for `--json`.

This tool controls printers on your local network. Do not expose the printer websocket port to the public internet.

## Protocol support

The client currently supports status, attributes, file listing, start, pause, resume, and stop commands. Starting a print may require printer-specific file/task metadata; use the printer web interface for upload and selection until that flow is standardized.

## Development

```powershell
py -m pytest
```

## License

MIT
