from typing import Callable


class Router:
    def __init__(self, prefix: str | None = None) -> None:
        self.prefix = prefix or ""
        self.routes: list[tuple[list[str], str, Callable]] = []

    def route(self, methods: list[str], pattern: str, handler: Callable) -> Callable:
        self.routes.append((methods, pattern, handler))
        return handler

    def get(self, pattern: str = "") -> Callable:
        def decorator(fn):
            self.routes.append((["GET"], pattern, fn))
            return fn

        return decorator

    def post(self, pattern: str = "") -> Callable:
        def decorator(fn):
            self.routes.append((["POST"], pattern, fn))
            return fn

        return decorator

    def put(self, pattern: str = "") -> Callable:
        def decorator(fn):
            self.routes.append((["PUT"], pattern, fn))
            return fn

        return decorator

    def delete(self, pattern: str = "") -> Callable:
        def decorator(fn):
            self.routes.append((["DELETE"], pattern, fn))
            return fn

        return decorator

    def patch(self, pattern: str = "") -> Callable:
        def decorator(fn):
            self.routes.append((["PATCH"], pattern, fn))
            return fn

        return decorator
