from http import HTTPStatus

from sevro import responses
from sevro.responses import Response


class HTTPException(Exception):
    def __init__(self, status: int, detail: str | None = None) -> None:
        self.status = status
        self.detail = detail or HTTPStatus(status).phrase
        super().__init__(self.detail)

    def response(self) -> Response:
        return responses.text(self.detail, self.status)


class ConversionError(HTTPException):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(422, detail)
