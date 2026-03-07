from typing import Any, Mapping, Union


from .base import Response
from .json import JSONResponse
from ..headers import MutableHeaders


def text(
    content: str,
    status: int = 200,
    headers: Union[MutableHeaders, dict[str, str]] | None = None,
) -> Response:
    return Response(content, status, media_type="text/plain", headers=headers)


def json(
    content: Mapping[str, Any],
    status: int = 200,
    headers: Union[MutableHeaders, dict[str, str]] | None = None,
) -> Response:
    return JSONResponse(content, status, media_type="application/json", headers=headers)
