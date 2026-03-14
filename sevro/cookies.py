from dataclasses import dataclass
from typing import Mapping

from sevro.headers import Headers, MutableHeaders


@dataclass
class Cookie:
    key: str
    value: str = ""
    max_age: int | None = None
    path: str = "/"
    domain: str | None = None
    secure: bool = False
    httponly: bool = False
    samesite: str = "lax"

    def encode(self) -> str:
        cookie = f"{self.key}={self.value}"
        if self.max_age is not None:
            cookie += f"; Max-Age={self.max_age}"
        if self.path:
            cookie += f"; Path={self.path}"
        if self.domain:
            cookie += f"; Domain={self.domain}"
        if self.secure:
            cookie += "; Secure"
        if self.httponly:
            cookie += "; HttpOnly"
        if self.samesite:
            cookie += f"; SameSite={self.samesite}"
        return cookie

    @staticmethod
    def _parse(cookie_str: str) -> Cookie:
        parts = [p.strip() for p in cookie_str.split(";")]
        key, _, value = parts[0].partition("=")
        kwargs = {}
        for part in parts[1:]:
            name, _, val = part.partition("=")
            match name.lower():
                case "max-age":
                    kwargs["max_age"] = int(val)
                case "path":
                    kwargs["path"] = val
                case "domain":
                    kwargs["domain"] = val
                case "samesite":
                    kwargs["samesite"] = val
                case "secure":
                    kwargs["secure"] = True
                case "httponly":
                    kwargs["httponly"] = True
        return Cookie(key=key, value=value, **kwargs)


class CookieJar(Mapping[str, Cookie]):
    def __init__(self, headers: Headers | None = None):
        self._cookies: dict[str, Cookie] = {}
        if headers is not None:
            for cookie in headers.getall("cookie"):
                cookie = Cookie._parse(cookie)
                self._cookies[cookie.key] = cookie

    def __len__(self):
        self._cookies.__len__()

    def __iter__(self):
        self._cookies.__iter__()

    def __getitem__(self, key, /):
        return self._cookies[key]

    def set(self, key: str, value: str, **kwargs) -> None:
        self._cookies[key] = Cookie(key, value, **kwargs)

    def delete(self, key: str, path: str = "/") -> None:
        self._cookies[key] = Cookie(key, "", max_age=0, path=path)

    def apply(self, headers: MutableHeaders) -> None:
        for cookie in self._cookies:
            headers.append("set-cookie", cookie.encode())
