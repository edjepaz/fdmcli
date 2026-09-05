"""Elegoo SDCP websocket client."""

from __future__ import annotations

import json
import time
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
