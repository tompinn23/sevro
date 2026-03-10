from http import HTTPStatus

from sevro.responses import text, HTTPResponse


class HTTPException(Exception):
    def __init__(self, status: int, detail: str | None = None) -> None:
        self.status = status
        self.detail = detail or HTTPStatus(status).phrase
        super().__init__(self.detail)

    def response(self) -> HTTPResponse:
        return text(self.detail, self.status)


class ConversionError(HTTPException):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(422, detail)
