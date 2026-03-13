import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, formatdate
from importlib.metadata import requires
from pathlib import Path, PurePath
from time import time
from typing import Any

import anyio
import orjson
from anyio.functools import cache

from .types import (
    BaseHTTPResponse,
    FileResponse,
    HTTPResponse,
    HeaderType,
    StreamResponse,
)
from ..headers import Headers, MutableHeaders

LOG = logging.getLogger("responses")


def redirect(
    url: str,
    status: int = 302,
    headers: HeaderType | None = None,
    cookies: CookieJar | None = None,
) -> HTTPResponse:
    headers = headers or MutableHeaders()
    headers.setdefault("location", url)
    return HTTPResponse(b"", status, headers)


def text(
    body: str,
    status: int = 200,
    headers: HeaderType | None = None,
    cookies: CookieJar | None = None,
    content_type: str = "text/plain; charset=utf-8",
) -> HTTPResponse:
    if not isinstance(body, str):
        raise TypeError(f"Bad body type. Expected str, got {type(body).__name__}")
    return HTTPResponse(body, status=status, headers=headers, content_type=content_type)


def json(
    body: Any,
    status: int = 200,
    headers: HeaderType | None = None,
    cookies: CookieJar | None = None,
    content_type: str = "application/json; charset=utf-8",
) -> HTTPResponse:
    return HTTPResponse(
        body=orjson.dumps(body),
        status=status,
        headers=headers,
        content_type=content_type,
    )


async def validate_file(
    headers: Headers, last_modified: datetime | float | int
) -> HTTPResponse | None:
    try:
        if_modified_since = headers.get("If-Modified-Since")
    except KeyError:
        return None
    try:
        if_modified_since = parsedate_to_datetime(if_modified_since)
    except (TypeError, ValueError):
        LOG.warning(
            "Ignorning invalid If-Modified-Since header received: '%s'",
            if_modified_since,
        )
        return None
    if not isinstance(last_modified, datetime):
        last_modified = datetime.fromtimestamp(
            float(last_modified), tz=timezone.utc
        ).replace(microsecond=0)

    if last_modified.utcoffset() is None and if_modified_since.utcoffset() is not None:
        LOG.warning("Cannot compare tz-aware and tz-naive datetimes. Converting to UTC")
        last_modified = last_modified.replace(tzinfo=timezone.utc)
    elif (
        last_modified.utcoffset() is not None and if_modified_since.utcoffset() is None
    ):
        LOG.warning("Cannot compare tz-aware and tz-naive datetimes. Converting to UTC")
        if_modified_since = if_modified_since.replace(tzinfo=timezone.utc)
    if last_modified.timestamp() <= if_modified_since.timestamp():
        return HTTPResponse(status=304)
    return None


async def file(
    path: str | PurePath,
    status: int = 200,
    headers: HeaderType | None = None,
    cookies: CookieJar | None = None,
    content_type: str = "application/octet-stream; charset=utf-8",
    request_headers: Headers | None = None,
    validate_requested: bool = True,
    filename: str | None = None,
    last_modified: datetime | int | None = -1,
    max_age: float | int | None = None,
    no_store: bool | None = None,
) -> HTTPResponse:
    if isinstance(last_modified, datetime):
        last_modified = last_modified.replace(microsecond=0).timestamp()
    elif isinstance(last_modified, int) and last_modified == -1:
        stat = await anyio.Path(path).stat(follow_symlinks=False)
        last_modified = stat.st_mtime

    if validate_requested and request_headers is not None and last_modified:
        response = await validate_file(request_headers, last_modified)
        if response:
            return response

    headers = headers or MutableHeaders()
    if last_modified:
        headers.setdefault("Last-Modified", formatdate(last_modified, usegmt=True))

    if filename:
        headers.setdefault("Content-Disposition", f'attachment; filename="{filename}"')

    if no_store:
        cache_control = "no-store"
    elif max_age:
        cache_control = f"public, max-age={max_age}"
        headers.setdefault("expires", formatdate(time() + max_age, usegmt=True))
    else:
        cache_control = "no-cache"

    headers.setdefault("cache-control", cache_control)
    return FileResponse(path, status=status, headers=headers, content_type=content_type)
