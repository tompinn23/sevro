import re
from collections.abc import Iterable
from typing import Callable, Any


class Routes:
    def __init__(self, prefix: str | None = None) -> None:
        self.prefix = prefix or ""
        self._routes: dict[tuple[str, str], Callable[..., Any]] = {}

    def __get_decorator(self, method: list[str] | str, pattern: str) -> Callable[..., Any]:
        if isinstance(method, list):
            def decorator(fn):
                for m in method:
                    self._routes[(m, self.__normalize(pattern))] = fn
                return fn
        else:
            def decorator(fn):
                self._routes[(method, self.__normalize(pattern))] = fn
                return fn

        return decorator

    def __normalize(self, pattern: str) -> str:
        if pattern == "":
            return self.prefix
        else:
            return re.sub(r'/+', '/', self.prefix + pattern)

    def routes(self) -> Iterable[tuple[str, str, Callable[..., Any]]]:
        for (m, p), v in self._routes.items():
            yield m,p,v


    def route(self, methods: list[str], pattern: str = "") -> Callable:
        return self.__get_decorator(methods, pattern)

    def get(self, pattern: str = "") -> Callable:
        return self.__get_decorator("GET", pattern)


    def post(self, pattern: str = "") -> Callable:
        return self.__get_decorator("POST", pattern)


    def put(self, pattern: str = "") -> Callable:
        return self.__get_decorator("PUT", pattern)

    def delete(self, pattern: str = "") -> Callable:
        return self.__get_decorator("DELETE", pattern)

    def patch(self, pattern: str = "") -> Callable:
        return self.__get_decorator("PATCH", pattern)

    def options(self, pattern: str = "") -> Callable:
        return self.__get_decorator("OPTIONS", pattern)

    def head(self, pattern: str = "") -> Callable:
        return self.__get_decorator("HEAD", pattern)

    def mount(self, router: Routes, /, prefix: str = ""):
        for method, pattern, handler in router.routes():
            k = (method, self.__normalize(prefix + pattern))
            if k in self._routes:
                raise KeyError(f"duplicate route {k}")
            self._routes[(method, self.__normalize(prefix + pattern))] = handler

    def __repr__(self):
        return f"Routes(prefix: {self.prefix}, routes: {self._routes})"

