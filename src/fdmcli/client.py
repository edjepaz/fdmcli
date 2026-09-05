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
            ws = websocket.create_connection(self.url, timeout=self.timeout)
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
            while time.monotonic() < deadline:
                response = json.loads(ws.recv())
                topic = response.get("Topic", "")
                if (
                    request_id == response.get("Data", {}).get("RequestID")
                    or "response" in topic
                    or "status" in topic
                    or "attributes" in topic
                ):
                    return response
            raise PrinterError("Timed out waiting for a printer response")
        except (OSError, websocket.WebSocketException, json.JSONDecodeError) as exc:
            raise PrinterError(f"Unable to communicate with printer: {exc}") from exc
        finally:
            if ws is not None:
                ws.close()
