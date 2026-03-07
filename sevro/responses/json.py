from typing import Any, Mapping, Union

import xxjson

from sevro.headers import MutableHeaders
from sevro.responses import Response


class JSONResponse(Response):
    def __init__(
        self,
        body: Mapping[str, Any],
        status: int = 200,
        headers: Union[MutableHeaders, dict[str, str]] | None = None,
        media_type: str | None = None,
    ) -> None:
        super().__init__(xxjson.dumps(body), status, media_type, headers)
