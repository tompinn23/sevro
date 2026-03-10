from typing import Any, AsyncGenerator

import xxjson

from ._types import RSGIProtocol, Scope, ASGIScope, ASGIReceive

from sevro import url


class Request:
    __slots__ = ("protocol", "scope")
    __eq__ = object.__eq__
    __hash__ = object.__hash__

    def __init__(self, scope: Scope | ASGIScope, protocol: Protocol | ASGIReceive):
        self.scope = scope
        self.protocol = protocol

    @property
    def url(self) -> url.URL:
        if not hasattr(self, "_url"):
            if isinstance(self.scope, dict):
                self._url = url.from_asgi_scope(self.scope)
            else:
                self._url = url.from_scope(self.scope)
        return self._url

    @property
    def params(self) -> dict[str, str]:
        return self.url.query()

    async def stream(self) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError

    async def body(self, max_size: int = 1024 * 1024 * 16) -> bytes:
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
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = xxjson.loads(body)
        return self._json


class RSGIRequest(Request):
    def __init__(self, scope: Scope, protocol: Protocol) -> None:
        assert scope.proto == "http"
        super().__init__(scope, protocol)

    async def stream(self) -> AsyncGenerator[bytes, None]:
        async for chunk in self.protocol:
            yield chunk


class ASGIRequest(Request):
    def __init__(self, scope: ASGIScope, receive: ASGIReceive) -> None:
        assert scope["type"] == "http"
        super().__init__(scope, receive)

    async def stream(self) -> AsyncGenerator[bytes, None]:
        while True:
            message = await self.protocol()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    yield body
                if not message.get("more_body", False):
                    break
