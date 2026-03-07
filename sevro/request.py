from typing import Any, AsyncGenerator

import xxjson

from ._types import Protocol, Scope

from sevro import url


class HTTPConnection:
    __slots__ = ("protocol", "scope")
    __eq__ = object.__eq__
    __hash__ = object.__hash__

    def __init__(self, scope: Scope, protocol: Protocol):
        assert scope.proto in ("http", "websocket")
        self.scope = scope
        self.protocol = protocol

    @property
    def url(self) -> url.URL:
        if not hasattr(self, "_url"):
            self._url = url.from_scope(self.scope)
        return self._url


class Request(HTTPConnection):
    def __init__(self, scope: Scope, protocol: Protocol) -> None:
        super().__init__(scope, protocol)
        assert scope.proto == "http"

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Asynchronously yield chunks of the request body.

        This method provides an async generator that yields bytes objects representing
        the incoming request body data as it is received from the client.
        """
        async for chunk in self.protocol:
            yield chunk

    async def body(self, max_size: int = 1024 * 1024 * 16) -> bytes:
        """Asynchronously read and return the entire request body as bytes.

        This method collects all chunks from the request stream and returns the complete body.
        """  # noqa: E501
        if not hasattr(self, "_body"):
            chunks: list[bytes] = []
            total_size = 0
            async for chunk in self.stream():
                total_size += len(chunk)
                if total_size > max_size:
                    raise ValueError(
                        f"Request body too large: {total_size} > {max_size}"
                    )
                chunks.append(chunk)
            self._body = b"".join(chunks)
        return self._body

    async def json(self) -> Any:
        """Asynchronously parse and return the request body as JSON.

        This method reads the request body and deserializes it using orjson,
        returning the parsed JSON object.
        """
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = xxjson.loads(body)
        return self._json
