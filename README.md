# fdmcli

`fdmcli` is a small command-line client for Elegoo network 3D printers that expose the local SDCP websocket protocol. It has been tested with the Elegoo Centauri Carbon.

## Install

```powershell
py -m pip install fdmcli
```

For development:

```powershell
py -m pip install -e ".[test]"
```

## Usage

```powershell
fdm --host 192.168.1.249 status
fdm --host 192.168.1.249 attributes
fdm --host 192.168.1.249 files
fdm --host 192.168.1.249 pause
fdm --host 192.168.1.249 resume
fdm --host 192.168.1.249 stop
```

The default host is `192.168.1.249`; override it with `--host`. Responses are printed as JSON, making the tool suitable for scripts:

```powershell
fdm --host printer.local --compact status | ConvertFrom-Json
```

This tool controls printers on your local network. Do not expose the printer websocket port to the public internet.

## Protocol support

The client currently supports status, attributes, file listing, start, pause, resume, and stop commands. Starting a print may require printer-specific file/task metadata; use the printer web interface for upload and selection until that flow is standardized.

## Development

```powershell
py -m pytest
```

## License

MIT
