from pathlib import Path
from typing import Protocol

import anyio

from sevro._types import ASGISend, RSGIProtocol, RSGIStreamTransport
from sevro.headers import MutableHeaders


class Sender(Protocol):
    async def write_status(
        self, status: int = 200, headers: MutableHeaders | None = None
    ): ...

    async def write(self, body: bytes | memoryview | str, more: bool = False): ...

    async def send_file(self, path: str | Path, stream: bool = False): ...


class RSGISender:
    def __init__(self, scope, rsgi: RSGIProtocol = None):
        self.scope = scope
        self.rsgi = rsgi

        self._stream: RSGIStreamTransport | None = None
        self._headers = None
        self._status = None
        self._written_headers = False

    async def write_status(
        self, status: int = 200, headers: MutableHeaders | None = None
    ):
        self._headers = headers
        self._status = status

    async def write(self, body: bytes | memoryview | str, more: bool = False):
        if not more and not self._written_headers:
            if self._headers is None or self._status is None:
                raise ValueError(
                    "Headers and status code must be specified before writing"
                )
            if body is None:
                self.rsgi.response_empty(self._status, self._headers.items())
            elif isinstance(body, str):
                self.rsgi.response_str(self._status, self._headers.items(), body)
            else:
                self.rsgi.response_bytes(self._status, self._headers.items(), body)
            self._written_headers = True
        elif more:
            if not self._written_headers:
                if self._headers is None or self._status is None:
                    raise ValueError(
                        "Headers and status code must be specified before writing"
                    )
                self._stream = self.rsgi.response_stream(
                    self._status, self._headers.items()
                )
                self._written_headers = True
            if isinstance(body, str):
                await self._stream.send_str(body)
            else:
                await self._stream.send_bytes(body)
        else:
            await self._stream.send_bytes(b"")

    async def send_file(self, path: str | Path, stream: bool = False):
        if self._headers is None or self._status is None:
            raise ValueError("Headers and status code must be specified before writing")
        self.rsgi.response_file(self._status, self._headers.items(), path)


class ASGISender:
    def __init__(self, scope, send: ASGISend):
        self.scope = scope
        self.send = send

        self._written_headers = False

    async def write_status(
        self, status: int = 200, headers: MutableHeaders | None = None
    ):
        await self.send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers.raw,
            }
        )
        self._written_headers = True

    async def write(self, body: bytes | memoryview | str, more: bool = False):
        if not self._written_headers:
            raise ValueError("Headers must be written first")
        if body is None:
            body = b""
        await self.send(
            {
                "type": "http.response.body",
                "body": body.encode() if isinstance(body, str) else body,
                "more_body": more,
            }
        )

    async def send_file(self, path: str | Path, stream: bool = False):
        if not self._written_headers:
            raise ValueError("Headers must be written first")
        if (
            "extensions" in self.scope
            and "http.response.pathsend" in self.scope["extensions"]
        ):
            await self.send({"type": "http.response.pathsend", "path": path})
        else:
            async with await anyio.open_file(path, "rb") as file:
                if stream:
                    while chunk := await file.read(65536):
                        await self.send(
                            {
                                "type": "http.response.body",
                                "body": chunk,
                                "more_body": True,
                            }
                        )
                    await self.send(
                        {"type": "http.response.body", "body": b"", "more_body": False}
                    )
                else:
                    await self.send(
                        {"type": "http.response.body", "body": await file.read()}
                    )
