from typing import Any, Union

from sevro._types import Protocol
from sevro.headers import MutableHeaders


class Response:
    _status: int
    _body: bytes
    _headers: MutableHeaders
    _media_type: str | None

    def __init__(
        self,
        body: Any | None = None,
        status: int = 200,
        headers: Union[MutableHeaders, dict[str, str]] | None = None,
        media_type: str | None = None,
    ) -> None:
        if body is None:
            self._body = b""
        else:
            self._body = body.encode() if hasattr(body, "encode") else body
        self._status = status
        if isinstance(headers, MutableHeaders):
            self._headers = headers
        else:
            self._headers = MutableHeaders(headers)
        self._media_type = media_type

    async def rsgi(self, proto: Protocol):
        if self._body is not None:
            self._headers["content-type"] = self._media_type
            self._headers["content-length"] = str(len(self._body))
            proto.response_bytes(self._status, self._headers.items(), self._body)
        if self._body is None:
            proto.response_empty(self._status, self._headers.items())

    async def asgi(self, send):
        if self._body is not None:
            self._headers["content-type"] = self._media_type
            self._headers["content-length"] = str(len(self._body))
        await send(
            {
                "type": "http.response.start",
                "status": self._status,
                "headers": self._headers.raw,
            }
        )
        await send({"type": "http.response.body", "body": self._body})
