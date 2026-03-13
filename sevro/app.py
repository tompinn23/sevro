import asyncio
from contextlib import AsyncExitStack
from functools import wraps
from typing import Callable, Any

from . import responses
from .depends import Dependant, get_dependant, solve_dependencies
from .exception import ConversionError, HTTPException
from sevro.responses.protocol import ASGISender, RSGISender
from .request import Request, RSGIRequest, ASGIRequest
from ._types import Scope, RSGIProtocol, ASGIScope, ASGIReceive, ASGISend
from .router import Router

from .subrouter import Router as SubRouter


class Application:
    router: Router

    def __init__(self):
        self.router = Router()
        self._registry: dict[type, Any] = {}
        self._startup: Callable | None = None
        self._shutdown: Callable | None = None

    def register(self, t: type, value: Any) -> None:
        self._registry[t] = value

    def on_startup(self, fn: Callable) -> Callable:
        self._startup = fn
        return fn

    def on_shutdown(self, fn: Callable) -> Callable:
        self._shutdown = fn
        return fn

    def mount(self, router: SubRouter | str, path: str | None = None) -> None:
        if isinstance(router, str):
            module_path, attr = (
                router.rsplit(":", 1) if ":" in router else (router, "routes")
            )
            import importlib

            router = getattr(importlib.import_module(module_path), attr)
        prefix = (path or "") + router.prefix
        for methods, pattern, fn in router.routes:
            full_path = prefix + pattern
            dependant = get_dependant(path=full_path, call=fn)
            self.router.route(methods, full_path, self._wrap(fn, dependant))

    def __get_decorator(self, method: str, pattern: str) -> Callable[..., Any]:
        def decorator(fn):
            route = pattern
            dependant = get_dependant(path=route, call=fn)
            self.router.route([method], route, self._wrap(fn, dependant))
            return fn

        return decorator

    def _wrap(self, f: Callable[..., Any], dependant: Dependant) -> Callable[..., Any]:
        @wraps(f)
        async def wrapper(req: Request, path_params: dict[str, str]):
            async with AsyncExitStack() as stack:
                solved = await solve_dependencies(
                    request=req,
                    dependant=dependant,
                    path_params=path_params,
                    async_exit_stack=stack,
                    registry=self._registry,
                )
            if solved.errors:
                raise ConversionError("; ".join(solved.errors))
            return await f(**solved.values)

        return wrapper

    async def _handle_lifespan(self, receive: ASGIReceive, send: ASGISend) -> None:
        message = await receive()
        if message["type"] == "lifespan.startup":
            try:
                if self._startup is not None:
                    if asyncio.iscoroutinefunction(self._startup):
                        await self._startup()
                    else:
                        self._startup()
                await send({"type": "lifespan.startup.complete"})
            except Exception as e:
                await send({"type": "lifespan.startup.failed", "message": str(e)})
                return
        message = await receive()
        if message["type"] == "lifespan.shutdown":
            try:
                if self._shutdown is not None:
                    if asyncio.iscoroutinefunction(self._shutdown):
                        await self._shutdown()
                    else:
                        self._shutdown()
                await send({"type": "lifespan.shutdown.complete"})
            except Exception as e:
                await send({"type": "lifespan.shutdown.failed", "message": str(e)})

    def get(self, pattern: str | None = None):
        return self.__get_decorator("GET", pattern)

    async def process(self, request, sender):
        url = request.url
        if match := self.router.find(url.path(), request.method):
            handler, params = match
            try:
                res = await handler(request, params)
            except HTTPException as e:
                res = e.response()
            except Exception as e:
                res = responses.text(str(e), 500)

            await res.send(sender)
        else:
            await responses.text("Not Found", 404).send(sender)

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend):
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return
        if scope["type"] != "http":
            return
        request = ASGIRequest(scope, receive)
        sender = ASGISender(scope, send)
        await self.process(request, sender)

    def __rsgi_init__(self, loop: asyncio.AbstractEventLoop):
        if self._startup is not None:
            if self._startup is not None:
                if asyncio.iscoroutinefunction(self._startup):
                    loop.run_until_complete(self._startup())
                else:
                    self._startup()

    def __rsgi_del__(self, loop):
        if self._shutdown is not None:
            if asyncio.iscoroutinefunction(self._shutdown):
                loop.run_until_complete(self._shutdown())
            else:
                self._shutdown()

    async def __rsgi__(self, scope: Scope, protocol: RSGIProtocol):
        request = RSGIRequest(scope, protocol)
        sender = RSGISender(scope, protocol)
        await self.process(request, sender)
