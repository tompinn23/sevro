import inspect
from functools import wraps
from typing import Callable, Any, Mapping

from . import responses
from .exception import ConversionError, HTTPException
from .converters import Converters
from .responses import Response
from .router import Router
from .request import Request
from ._types import Scope, Protocol


class Application:
    router: Router
    converters: Converters

    def __init__(self):
        self.router = Router()
        self.converters = Converters()

    def __get_decorator(
        self, method: str, pattern: str | None = None
    ) -> Callable[..., Any]:
        def decorator(fn):
            route = pattern
            if route is None:
                route = (
                    "/"
                    if fn.__name__ in ("index", "default")
                    else "/" + fn.__name__.replace("_", "-")
                )
            self.router.route([method], route, self._wrap(fn))
            return fn

        return decorator

    def _wrap(self, f: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(f)
        params = list(sig.parameters.values())

        plan = []
        for p in params:
            if p.annotation is Request:
                plan.append(("conn", p.name, None))
            elif p.annotation is str:
                plan.append(("raw", p.name, None))
            elif p.annotation is not inspect.Parameter.empty:
                converter = self.converters.strategy(str, p.annotation)  # resolved once
                plan.append(("convert", p.name, converter))
            else:
                raise TypeError(
                    f"Parameter '{p.name}' in {f.__name__} has no annotation"
                )

        @wraps(f)
        def wrapper(req, param_map: dict[str, str]):
            args = []
            for kind, name, cv in plan:
                if kind == "conn":
                    args.append(req)
                elif kind == "raw":
                    args.append(param_map[name])
                else:
                    try:
                        args.append(cv(param_map[name]))
                    except (ValueError, TypeError) as e:
                        raise ConversionError(
                            f"Could not convert param '{name}' value {param_map[name]!r} "
                            f"to {converter.__name__}: {e}"
                        ) from e
            return f(*args)

        return wrapper

    def get(self, pattern: str | None = "/"):
        return self.__get_decorator("GET", pattern)

    async def __rsgi__(self, scope: Scope, protocol: Protocol):
        request = Request(scope, protocol)
        url = request.url
        if match := self.router.find(url.path(), scope.method):
            handler, params = match
            try:
                res = await handler(request, params)
            except HTTPException as e:
                res = e.response()
            except Exception as e:
                res = responses.text(str(e), 500)

            if isinstance(res, Response):
                await res.rsgi(protocol)
            elif isinstance(res, str):
                await responses.text(res).rsgi(protocol)
            elif isinstance(res, Mapping):
                await responses.json(res).rsgi(protocol)
        else:
            await responses.text("Not Found", 404).rsgi(protocol)
