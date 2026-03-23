from sevro.core import URL

from sevro._types import Scope, ASGIScope

def parse(url: str) -> URL:
    return URL(url)

def from_asgi_scope(scope: ASGIScope) -> URL:
    scheme = scope.get("scheme", "http")
    path = scope["path"]
    query_string = scope["query_string"].decode("latin-1")
    server = scope.get("server")

    host_header = None
    for key, value in scope.get("headers", []):
        if key == b"host":
            host_header = value.decode("latin-1")
            break

    if host_header is not None:
        url = f"{scheme}://{host_header}{path}"
    elif server is None:
        url = path
    else:
        host, port = server
        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
        if port == default_port:
            url = f"{scheme}://{host}{path}"
        else:
            url = f"{scheme}://{host}:{port}{path}"

    if query_string:
        url += "?" + query_string

    return URL(url)


def from_scope(scope: Scope) -> URL:
    scheme = scope.scheme
    server = scope.server
    path = scope.path
    query_string = scope.query_string

    host_header = None
    for key, value in scope.headers.items():
        if key == b"host":
            host_header = value.decode("latin-1")
            break

    if host_header is not None:
        url = f"{scheme}://{host_header}{path}"
    elif server is None:
        url = path
    else:
        host, port = server.split(":")
        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
        if port == default_port:
            url = f"{scheme}://{host}{path}"
        else:
            url = f"{scheme}://{host}:{port}{path}"

    if query_string:
        url += "?" + query_string

    return URL(url)
