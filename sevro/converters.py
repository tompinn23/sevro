from typing import TypeVar, Callable

import orjson

S = TypeVar("S")
D = TypeVar("D")


class Converters:
    _strategies: dict[tuple[type, type], Callable]

    def __init__(self):
        self._strategies = {}

        self.register(str, dict, orjson.loads)

    def register(self, src: S, dst: D, converter: Callable[[S], D]):
        self._strategies[(src, dst)] = converter

    def strategy(self, src: type[S], dest: type[D]) -> Callable[[S], D]:
        key = (src, dest)
        if key in self._strategies:
            return self._strategies[key]
        if src is str:
            return dest
        raise LookupError(
            f"No conversion strategy from {src.__name__} to {dest.__name__}"
        )
