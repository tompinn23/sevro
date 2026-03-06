from pathlib import Path
from typing import Union

from sevro.headers import MutableHeaders
from .base import Response
from .._types import Protocol

import mimetypes


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

    def _set_headers(self):
        if self._media_type is None:
            mime_type, encoding = mimetypes.guess_file_type(self._path)
            self._headers["content-type"] = mime_type or "application/octet-stream"
            if encoding:
                self._headers["content-encoding"] = encoding
        # if "content-length" not in self._headers:
        #     self._headers["content-length"] = "0"

    async def rsgi(self, proto: Protocol):
        self._set_headers()
        proto.response_file(self._status, self._headers.items(), self._path)

    async def asgi(self, send):
        await send(
            {
                "type": "http.response.start",
                "status": self._status,
                "headers": self._headers.raw,
            }
        )
        await send({"type": "http.response.body", "body": self._body})
