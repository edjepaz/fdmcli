# fdmcli

`fdmcli` is a friendly command-line client for Elegoo network 3D printers that expose the local SDCP websocket protocol. It has been tested with the Elegoo Centauri Carbon.

## Install

### Windows executable

Download `fdm-windows-x64.exe` from the latest [GitHub release](https://github.com/edjepaz/fdmcli/releases/latest), rename it to `fdm.exe`, and put it on your `PATH`. No Python installation is required.

The executable can update itself:

```powershell
fdm upgrade
fdm upgrade v0.4.0
```

### Python

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
fdm info
fdm files
fdm ls
fdm pause
fdm resume
fdm stop
fdm web --open
```

Check the installed version and automatically check GitHub for a newer release:

```powershell
fdm --version
fdm version
```

List all stable published versions:

```powershell
fdm versions
fdm versions --json
```

`fdm upgrade` installs the latest stable release. Pass a tag to upgrade or downgrade to an exact version. The executable updates itself; Python installations use pip.

The default host is `192.168.1.249`, so the shortest command is `fdm status`. Override it with `--host` when using another printer:

```powershell
fdm --host printer.local status
```

You can also set a default printer without repeating options:

```powershell
$env:FDM_HOST = "printer.local"
$env:FDM_PORT = "3030"
fdm status
```

`FDM_HOST`, `FDM_PORT`, and `FDM_TIMEOUT` are supported. Command-line options always take precedence.

Human-readable output is the default. Use `--json` for scripts:

```powershell
fdm --json status | ConvertFrom-Json
fdm --json --host printer.local status > status.json
```

Interactive output uses a compact terminal layout with colors, status highlights, and progress bars. Colors automatically turn off when output is redirected. Disable them explicitly with `--no-color`, or set the standard `NO_COLOR` environment variable.

```powershell
fdm --no-color status
```

Run `fdm --help` or `fdm status --help` for built-in guidance. Help is organized into connection, output, and command sections. `info` is an alias for `attributes`, and `ls`/`list` are aliases for `files`. The older `--compact` flag remains accepted as an alias for `--json`.

If you mistype a command, the CLI suggests the closest valid command. For example, use `fdm ls` or `fdm list` to list printer files.

To open the printer's built-in web interface:

```powershell
fdm web
fdm web --open
```

The commands that change print state (`start`, `pause`, `resume`, and `stop`) should be used intentionally. The printer may reject `start` unless a file has already been selected in its web interface.

## Printing from the CLI

Upload a sliced G-code file without starting it:

```powershell
fdm upload .\model.gcode
```

Upload a file and start printing it. `fdm` asks for confirmation because this starts a real print:

```powershell
fdm print .\model.gcode
```

For scripts or unattended use:

```powershell
fdm print .\model.gcode --yes
```

The file must be a `.gcode` file. The CLI uploads it in 1 MiB chunks, refreshes the printer file list, and starts the uploaded file using the printer's local SDCP protocol. It does not slice STL/3MF files; slice them first in your usual slicer.

This tool controls printers on your local network. Do not expose the printer websocket port to the public internet.

## Protocol support

The client currently supports status, attributes, file listing, start, pause, resume, and stop commands. Starting a print may require printer-specific file/task metadata; use the printer web interface for upload and selection until that flow is standardized.

## Development

```powershell
py -m pytest
```

## License

MIT
