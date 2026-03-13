import mimetypes
from typing import Any, Union

import anyio
from sevro.cookies import CookieJar

from sevro.headers import MutableHeaders
from sevro.responses.protocol import Sender

HeaderType = Union[MutableHeaders, dict[str, str]]

STREAM_THRESHOLD = 256 * 1024


class BaseHTTPResponse:
    def __init__(self):
        self.body: Any | None = None
        self.content_type: str | None = None
        self.status: int = None
        self.headers = MutableHeaders()


class HTTPResponse(BaseHTTPResponse):
    def __init__(
        self,
        body: Any = None,
        status: int = 200,
        headers: HeaderType | None = None,
        cookies: CookieJar | None = None,
        content_type: str | None = None,
    ):
        super().__init__()
        self.body = body
        self.status = status
        self.headers = (
            MutableHeaders(headers)
            if isinstance(headers, dict)
            else headers or MutableHeaders()
        )
        if cookies is not None:
            cookies.apply(self.headers)
        self.content_type = content_type

    async def send(self, protocol: Sender):
        if self.content_type:
            self.headers["content-type"] = self.content_type
        await protocol.write_status(self.status, self.headers)
        await protocol.write(self.body, more=False)


class StreamResponse(BaseHTTPResponse):
    def __init__(
        self,
        body: Any = None,
        status: int = 200,
        headers: HeaderType | None = None,
        cookies: CookieJar | None = None,
        content_type: str | None = None,
    ):
        super().__init__()
        self.body = body
        self.status = status
        self.headers = (
            MutableHeaders(headers)
            if isinstance(headers, dict)
            else headers or MutableHeaders()
        )
        if cookies is not None:
            cookies.apply(self.headers)
        self.content_type = content_type

    async def send(self, protocol: Sender):
        if self.content_type:
            self.headers["content-type"] = self.content_type
        await protocol.write_status(self.status, self.headers)
        if hasattr(self.body, "__aiter__"):
            async for chunk in self.body:
                await protocol.write(chunk, more=True)
            await protocol.write(b"", more=False)
        else:
            raise TypeError("Body is not an async generator")


class FileResponse(HTTPResponse):
    def __init__(
        self,
        path: str,
        status: int = 200,
        headers: HeaderType | None = None,
        cookies: CookieJar | None = None,
        content_type: str | None = None,
    ):
        super().__init__()
        self.path = path
        self.status = status
        self.headers = (
            MutableHeaders(headers)
            if isinstance(headers, dict)
            else headers or MutableHeaders()
        )
        if cookies is not None:
            cookies.apply(self.headers)
        self.content_type = content_type

    async def _set_headers(self) -> bool:
        if self.content_type is None:
            mime_type, encoding = mimetypes.guess_file_type(self.path)
            self.headers["content-type"] = mime_type or "application/octet-stream"
            if encoding:
                self.headers["content-encoding"] = encoding
        stat = await anyio.Path(self.path).stat()
        if stat.st_size <= STREAM_THRESHOLD:
            self.headers["content-length"] = str(stat.st_size)
            return True
        else:
            return False

    async def send(self, protocol: Sender):
        stream = await self._set_headers()
        await protocol.write_status(self.status, self.headers)
        await protocol.send_file(self.path, stream)
