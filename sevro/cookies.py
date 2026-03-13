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


class CookieJar:
    def __init__(self):
        self._cookies: list[Cookie] = []

    def set(self, key: str, value: str, **kwargs) -> None:
        self._cookies.append(Cookie(key, value, **kwargs))

    def delete(self, key: str, path: str = "/") -> None:
        self._cookies.append(Cookie(key, "", max_age=0, path=path))

    def apply(self, headers: MutableHeaders) -> None:
        for cookie in self._cookies:
            headers.append("set-cookie", cookie.encode())
