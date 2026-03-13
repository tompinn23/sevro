from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Guard:
    dependency: Callable
    required: bool  # True: raise 401 if result is None


class Router:
    def __init__(self, prefix: str | None = None) -> None:
        self.prefix = prefix or ""
        self.routes: list[tuple[list[str], str, Callable, list[Guard]]] = []

    def required(self, dependency: Callable) -> Callable:
        def decorator(fn: Callable) -> Callable:
            if not hasattr(fn, "_guards"):
                fn._guards = []
            fn._guards.append(Guard(dependency=dependency, required=True))
            return fn

        return decorator

    def optional(self, dependency: Callable) -> Callable:
        def decorator(fn: Callable) -> Callable:
            if not hasattr(fn, "_guards"):
                fn._guards = []
            fn._guards.append(Guard(dependency=dependency, required=False))
            return fn

        return decorator

    def route(self, methods: list[str], pattern: str, handler: Callable) -> Callable:
        guards: list[Guard] = getattr(handler, "_guards", [])
        self.routes.append((methods, pattern, handler, guards))
        return handler

    def get(self, pattern: str = "") -> Callable:
        def decorator(fn: Callable) -> Callable:
            guards: list[Guard] = getattr(fn, "_guards", [])
            self.routes.append((["GET"], pattern, fn, guards))
            return fn

        return decorator

    def post(self, pattern: str = "") -> Callable:
        def decorator(fn: Callable) -> Callable:
            guards: list[Guard] = getattr(fn, "_guards", [])
            self.routes.append((["POST"], pattern, fn, guards))
            return fn

        return decorator

    def put(self, pattern: str = "") -> Callable:
        def decorator(fn: Callable) -> Callable:
            guards: list[Guard] = getattr(fn, "_guards", [])
            self.routes.append((["PUT"], pattern, fn, guards))
            return fn

        return decorator

    def delete(self, pattern: str = "") -> Callable:
        def decorator(fn: Callable) -> Callable:
            guards: list[Guard] = getattr(fn, "_guards", [])
            self.routes.append((["DELETE"], pattern, fn, guards))
            return fn

        return decorator

    def patch(self, pattern: str = "") -> Callable:
        def decorator(fn: Callable) -> Callable:
            guards: list[Guard] = getattr(fn, "_guards", [])
            self.routes.append((["PATCH"], pattern, fn, guards))
            return fn

        return decorator