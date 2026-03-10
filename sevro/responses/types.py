from typing import Any, Union

from sevro._types import RSGIProtocol
from sevro.headers import MutableHeaders
from sevro.protocol import Sender


class BaseHTTPResponse:

    def __init__(self):
        self.body: Any | None = None
        self.content_type: str | None = None
        self.status: int = None
        self.headers = MutableHeaders()


class HTTPResponse(BaseHTTPResponse):

    def __init__(self, body: Any = None, status: int = 200, headers: MutableHeaders | dict[str, str] | None = None,
                 content_type: str | None = None):
        super().__init__()
        self.body = body
        self.status = status
        self.headers = MutableHeaders(headers) if isinstance(headers, dict) else headers
        self.content_type = content_type

    async def send(self, protocol: Sender):
        await protocol.write_status(self.status, self.headers)
        await protocol.write(self.body, more=False)

class StreamResponse(BaseHTTPResponse):
    def __init__(self, body: Any = None, status: int = 200, headers: MutableHeaders | dict[str, str] | None = None,
                 content_type: str | None = None):
        super().__init__()
        self.body = body
        self.status = status
        self.headers = MutableHeaders(headers) if isinstance(headers, dict) else headers
        self.content_type = content_type

    async def send(self, protocol: Sender):
        await protocol.write_status(self.status, self.headers)
        if hasattr(self.body, "__aiter__"):
            async for chunk in self.body:
                await protocol.write(chunk, more=True)
            await protocol.write(b"", more=False)
        else:
            raise TypeError("Body is not an async generator")
