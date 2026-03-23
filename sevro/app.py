import asyncio
import logging
import sys
from contextlib import AsyncExitStack
from functools import wraps
from typing import Callable, Any

from . import responses
from .depends import Dependant, get_dependant, solve_dependencies
from .exception import ConversionError, HTTPException
from sevro.responses.protocol import ASGISender, RSGISender
from .request import Request, RSGIRequest, ASGIRequest
from ._types import Scope, RSGIProtocol, ASGIScope, ASGIReceive, ASGISend

from .core import Router

LOG = logging.getLogger(__name__)

async def _base_error(request: Request, err: Exception):
    LOG.error("Unhandled exception whilst processing request", exc_info=True)
    return responses.text(str(err), 500)


class Application:
    """
    Core Sevro application object.

    An Application manages:
    - dependency injection
    - middleware execution
    - error handlers

    One Application instance should be created per worker/process.
    """


    def __init__(self, routes: Routes):
        """
        Initialize the application.

        Parameters
        ----------
        routes : Routes
            A Routes object containing (method, path, handler) triples.
            These handlers are dependency-wrapped and registered in the router.

        Raises
        ------
        ValueError
            If `routes` is None.
        """

        if routes is None:
            raise ValueError("routes must not be none")
        self.router = Router()
        for method, path, fn in routes.routes():
            dependant = get_dependant(path, fn)
            self.router.route(method, path, self._wrap(fn, dependant))

        self._middlewares = []
        self._error_handlers: dict[type[BaseException], Callable[[Request, BaseException], HTTPResponse]] = {Exception: _base_error}
        self._registry: dict[type, Any] = {}
        self._startup: Callable | None = None
        self._shutdown: Callable | None = None

    def register(self, t: type, value: Any) -> None:
        """
        Register a type for dependency injection.
        Used for things such as db pools

        Parameters
        ----------
        t : type
            Type key under which the value is stored.
        value : Any
            Value instance to inject into handlers/middleware.
        """
        self._registry[t] = value

    def error_handler(self, exc_class: type[BaseException]):
        """
        Decorator that registers an error handler for a given exception,
        exceptions are propogated upwards until a valid handler is found.

        Parameters
        ----------
        exc_class: type[BaseException]
            The exception type to register a handler for. e.g. HTTPException/ValueError
        """
        def decorator(fn):
            self._error_handlers[exc_class] = fn
            return fn

        return decorator

    def on_startup(self, fn: Callable) -> Callable:
        """
        Set a startup hook this is called according to RSGI/ASGI lifespan/lifetime hooks.
        """
        self._startup = fn
        return fn

    def on_shutdown(self, fn: Callable) -> Callable:
        """
        Set a shutdown hook this is called according to RSGI/ASGI lifespan/lifetime hooks.
        """
        self._shutdown = fn
        return fn

    def register_middleware(self, mw: Callable[..., Any]):
        """
        Register a middleware for use in all routes, (route specific middlewares should use Depends)

        All global middleware must include a next parameter which is the next stage of the route, middleware's may
        choose to not continue the route by:
         - returning a response
         - raising an exception

        Middleware MUST return a value back up the chain or throw an Exception
        """
        dependant = get_dependant(path="", call=mw)
        assert dependant.next_param_name is not None, (
            f"Middleware '{fn.__name__}' must have a 'next: Callable' parameter"
        )
        self._middlewares.append((mw, dependant))

    def _wrap(
        self,
        call: Callable[..., Any],
        dependant: Dependant,
    ) -> Callable[..., Any]:
        @wraps(call)
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
            return await call(**solved.values)

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

    async def __process(self, request, sender):
        async def handle(req):
            url = req.url()
            if match := self.router.find(req.method(), url.path()):
                handler, params = match
                return await handler(req, params)
            return responses.text("Not Found", 404)

        next_fn = handle
        for mw_fn, mw_dep in reversed(self._middlewares):
            _fn, _dep, _next = mw_fn, mw_dep, next_fn

            async def call_mw(req, *, fn=_fn, dep=_dep, nxt=_next):
                async with AsyncExitStack() as stack:
                    solved = await solve_dependencies(
                        request=req,
                        dependant=dep,
                        path_params={},
                        async_exit_stack=stack,
                        registry=self._registry,
                    )
                if solved.errors:
                    raise ConversionError("; ".join(solved.errors))
                return await fn(**solved.values, **{dep.next_param_name: nxt})

            next_fn = call_mw

        try:
            res = await next_fn(request)
        except Exception as err:
            for cls in type(err).__mro__:
                if cls in self._error_handlers:
                    res = await self._error_handlers[cls](request, err)
                    break

        await res.send(sender)

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend):
        """
        ASGI entry point, handles protocol creation and takes the scope of the ASGI event into a request object
        """
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return
        if scope["type"] != "http":
            return
        request = ASGIRequest(scope, receive)
        sender = ASGISender(scope, send)
        await self.__process(request, sender)

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
        """
        RSGI entrypoint.
        """
        request = RSGIRequest(scope, protocol)
        sender = RSGISender(scope, protocol)
        await self.__process(request, sender)
