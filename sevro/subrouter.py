from typing import Callable


class Router:
    def __init__(self, prefix: str | None = None) -> None:
        self.prefix = prefix or ""
        self.routes: list[tuple[list[str], str, Callable]] = []

    def _resolve_path(self, pattern: str | None, fn: Callable) -> str:
        if pattern is not None:
            return pattern
        return (
            "/"
            if fn.__name__ in ("index", "default")
            else "/" + fn.__name__.replace("_", "-")
        )

    def route(self, methods: list[str], pattern: str, handler: Callable) -> Callable:
        self.routes.append((methods, pattern, handler))
        return handler

    def get(self, pattern: str | None = None) -> Callable:
        def decorator(fn):
            self.routes.append((["GET"], self._resolve_path(pattern, fn), fn))
            return fn

        return decorator

    def post(self, pattern: str | None = None) -> Callable:
        def decorator(fn):
            self.routes.append((["POST"], self._resolve_path(pattern, fn), fn))
            return fn

        return decorator

    def put(self, pattern: str | None = None) -> Callable:
        def decorator(fn):
            self.routes.append((["PUT"], self._resolve_path(pattern, fn), fn))
            return fn

        return decorator

    def delete(self, pattern: str | None = None) -> Callable:
        def decorator(fn):
            self.routes.append((["DELETE"], self._resolve_path(pattern, fn), fn))
            return fn

        return decorator

    def patch(self, pattern: str | None = None) -> Callable:
        def decorator(fn):
            self.routes.append((["PATCH"], self._resolve_path(pattern, fn), fn))
            return fn

        return decorator
