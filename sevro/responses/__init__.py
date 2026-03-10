from typing import Any

import xxjson

from .types import BaseHTTPResponse, HTTPResponse, StreamResponse
from ..headers import MutableHeaders

HeaderType = MutableHeaders | dict[str, str]


def text(body: str,
         status: int = 200,
         headers: HeaderType | None = None,
         content_type: str = "text/plain; charset=utf-8") -> HTTPResponse:
    if not isinstance(body, str):
        raise TypeError(f"Bad body type. Expected str, got {type(body).__name__}")
    return HTTPResponse(
        body, status=status, headers=headers, content_type=content_type
    )

def json(body: Any,
         status: int = 200,
         headers: HeaderType | None = None,
         content_type: str = "application/json; charset=utf-8") -> HTTPResponse:
    return HTTPResponse(
        body=xxjson.dumps(body),
        status=status, headers=headers, content_type=content_type
    )




