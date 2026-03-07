from pathlib import Path
from typing import Union

import anyio

from sevro.headers import MutableHeaders
from .base import Response
from .._types import Protocol

import mimetypes

STREAM_THRESHOLD = 256 * 1024


class FileResponse(Response):
    def __init__(
        self,
        path: str | Path,
        status: int = 200,
        headers: Union[MutableHeaders, dict[str, str]] | None = None,
        media_type: str | None = None,
    ) -> None:
        super().__init__(None, status, headers, media_type)
        self._path = path

    async def _set_headers(self):
        if self._media_type is None:
            mime_type, encoding = mimetypes.guess_file_type(self._path)
            self._headers["content-type"] = mime_type or "application/octet-stream"
            if encoding:
                self._headers["content-encoding"] = encoding
        stat = await anyio.Path(self._path).stat()
        if stat.st_size <= STREAM_THRESHOLD:
            self._headers["content-length"] = str(stat.st_size)
            return stat.st_size
        else:
            self._headers["transfer-encoding"] = "chunked"
            return None

    async def rsgi(self, proto: Protocol):
        await self._set_headers()
        proto.response_file(self._status, self._headers.items(), self._path)

    async def asgi(self, scope, send):
        size = await self._set_headers()
        await send(
            {
                "type": "http.response.start",
                "status": self._status,
                "headers": self._headers.raw,
            }
        )
        if size is not None:
            async with await anyio.open_file(self._path, "rb") as f:
                body = await f.read()
            await send({"type": "http.response.body", "body": body})
        else:
            async with await anyio.open_file(self._path, "rb") as f:
                while chunk := await f.read(65536):
                    await send(
                        {"type": "http.response.body", "body": chunk, "more_body": True}
                    )
            await send({"type": "http.response.body", "body": b"", "more_body": False})
