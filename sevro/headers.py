from typing import Any, Mapping, MutableMapping


class Headers(Mapping[str, str]):
    def __init__(
        self,
        /,
        headers: Mapping[str, str] | None = None,
        scope: MutableMapping[str, Any] | None = None,
    ) -> None:
        if headers is not None:
            assert scope is None
            self._list = [
                (key.lower().encode("latin-1"), value.encode("latin-1"))
                for key, value in headers.items()
            ]
        elif scope is not None:
            self._list = scope["headers"] = list(scope["headers"])
        else:
            self._list = []

    @property
    def raw(self) -> list[tuple[str, str]]:
        return list(self._list)

    def values(self):
        return [v.decode("latin-1") for _, v in self._list]

    def keys(self):
        return [key.decode("latin-1") for key, _ in self._list]

    def items(self):
        return [(k.decode("latin-1"), v.decode("latin-1")) for k, v in self._list]

    def getall(self, key: str) -> list[str]:
        k = key.lower().encode("latin-1")
        return [v.decode("latin-1") for i, v in self._list if i == k]

    def __len__(self):
        return len(self._list)

    def __iter__(self):
        return iter(self.keys())

    def __getitem__(self, key: str, /) -> str:
        k = key.lower().encode("latin-1")
        for i, v in self._list:
            if i == k:
                return v.decode("latin-1")
        raise KeyError(key)

    def __contains__(self, key: Any) -> bool:
        get_header_key = key.lower().encode("latin-1")
        for header_key, header_value in self._list:
            if header_key == get_header_key:
                return True
        return False

    def __eq__(self, other, /):
        if not isinstance(other, Headers):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self):
        class_name = self.__class__.__name__
        as_dict = dict(self.items())
        if len(as_dict) == len(self):
            return f"{class_name}({as_dict!r})"
        return f"{class_name}(raw={self.raw!r})"


class MutableHeaders(Headers):
    def __setitem__(self, key: str, value: str) -> None:
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")

        found_indexes: list[int] = []
        for idx, (item_key, item_value) in enumerate(self._list):
            if item_key == set_key:
                found_indexes.append(idx)

        for idx in reversed(found_indexes[1:]):
            del self._list[idx]

        if found_indexes:
            idx = found_indexes[0]
            self._list[idx] = (set_key, set_value)
        else:
            self._list.append((set_key, set_value))

    def __delitem__(self, key: str) -> None:
        del_key = key.lower().encode("latin-1")

        pop_indexes: list[int] = []
        for idx, (item_key, item_value) in enumerate(self._list):
            if item_key == del_key:
                pop_indexes.append(idx)

        for idx in reversed(pop_indexes):
            del self._list[idx]

    def __ior__(self, other: Mapping[str, str]) -> MutableHeaders:
        if not isinstance(other, Mapping):
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        self.update(other)
        return self

    def __or__(self, other: Mapping[str, str]) -> MutableHeaders:
        if not isinstance(other, Mapping):
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        new = self.mutablecopy()
        new.update(other)
        return new

    def setdefault(self, key: str, value: str) -> str:
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")

        for idx, (item_key, item_value) in enumerate(self._list):
            if item_key == set_key:
                return item_value.decode("latin-1")
        self._list.append((set_key, set_value))
        return value

    def update(self, other: Mapping[str, str]) -> None:
        for key, val in other.items():
            self[key] = val

    def append(self, key: str, value: str) -> None:
        append_key = key.lower().encode("latin-1")
        append_value = value.encode("latin-1")
        self._list.append((append_key, append_value))
