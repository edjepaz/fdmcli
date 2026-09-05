"""Elegoo SDCP websocket client."""

from __future__ import annotations

import json
import hashlib
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import websocket


COMMANDS = {
    "status": 0,
    "attributes": 1,
    "start": 128,
    "pause": 129,
    "stop": 130,
    "resume": 131,
    "files": 258,
}
UPLOAD_CHUNK_SIZE = 1024 * 1024


class PrinterError(RuntimeError):
    """Raised when the printer cannot be reached or returns an error."""


class PrinterClient:
    """Client for the local Elegoo SDCP websocket endpoint."""

    def __init__(self, host: str, port: int = 3030, timeout: float = 10) -> None:
        self.url = f"ws://{host}:{port}/websocket"
        self.timeout = timeout

    def command(self, name: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in COMMANDS:
            raise ValueError(f"Unsupported command: {name}")

        ws = None
        try:
            ws = websocket.create_connection(
                self.url,
                timeout=self.timeout,
                skip_utf8_validation=True,
            )
            request_id = uuid.uuid4().hex
            message = {
                "Id": "",
                "Data": {
                    "Cmd": COMMANDS[name],
                    "Data": data or {},
                    "RequestID": request_id,
                    "MainboardID": "",
                    "TimeStamp": int(time.time() * 1000),
                    "From": 1,
                },
            }
            ws.send(json.dumps(message))
            deadline = time.monotonic() + self.timeout
            fallback: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                frame = ws.recv_frame()
                if frame.opcode == websocket.ABNF.OPCODE_PING:
                    ws.pong(frame.data)
                    continue
                if frame.opcode == websocket.ABNF.OPCODE_CLOSE:
                    raise PrinterError("Printer closed the websocket connection")
                if frame.opcode not in (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY):
                    continue
                raw = frame.data
                if isinstance(raw, bytes):
                    try:
                        raw = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        raw = raw.decode("latin-1")
                response = json.loads(raw)
                topic = response.get("Topic", "")
                if request_id == response.get("Data", {}).get("RequestID"):
                    fallback = response
                if name == "status" and "status" in topic:
                    return response
                if name == "attributes" and "attributes" in topic:
                    return response
                if name == "files" and "response" in topic:
                    return response
                if name not in {"status", "attributes", "files"} and "response" in topic:
                    return response
            if fallback is not None:
                return fallback
            raise PrinterError("Timed out waiting for a printer response")
        except (OSError, websocket.WebSocketException, json.JSONDecodeError) as exc:
            raise PrinterError(f"Unable to reach {self.url}: {exc}") from exc
        finally:
            if ws is not None:
                ws.close()

    def upload(self, path: str, on_progress: Any = None) -> dict[str, Any]:
        """Upload a G-code file using the printer's chunked HTTP endpoint."""
        if not path.lower().endswith(".gcode"):
            raise PrinterError("Only .gcode files can be uploaded")
        if not os.path.isfile(path):
            raise PrinterError(f"File not found: {path}")

        size = os.path.getsize(path)
        digest = hashlib.md5()
        with open(path, "rb") as source:
            while chunk := source.read(UPLOAD_CHUNK_SIZE):
                digest.update(chunk)
        upload_id = uuid.uuid4().hex
        name = os.path.basename(path)
        last_response: dict[str, Any] = {}
        with open(path, "rb") as source:
            offset = 0
            while offset < size:
                chunk = source.read(UPLOAD_CHUNK_SIZE)
                body, content_type = _multipart(
                    {
                        "TotalSize": str(size),
                        "Uuid": upload_id,
                        "Offset": str(offset),
                        "Check": "1",
                        "S-File-MD5": digest.hexdigest(),
                    },
                    "File",
                    name,
                    chunk,
                )
                request = urllib.request.Request(
                    f"http://{self.url.split('//', 1)[1].split(':', 1)[0]}:80/uploadFile/upload",
                    data=body,
                    headers={"Content-Type": content_type},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=self.timeout) as response:
                        raw = response.read()
                        last_response = json.loads(raw.decode("utf-8", errors="replace") or "{}")
                except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                    raise PrinterError(f"Upload failed for {name}: {exc}") from exc
                offset += len(chunk)
                if on_progress:
                    on_progress(offset / size)
        return last_response


def _multipart(fields: dict[str, str], field_name: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----fdmcli{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for key, value in fields.items():
        lines.extend(
            [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="{key}"'.encode(),
                b"",
                value.encode(),
            ]
        )
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    lines.extend(
        [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode(),
            f"Content-Type: {content_type}".encode(),
            b"",
            content,
            f"--{boundary}--".encode(),
            b"",
        ]
    )
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"
