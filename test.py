from typing import Annotated, Callable

import uvicorn

from sevro.app import Application
from sevro.depends import Depends
from sevro.request import Request

from sevro.responses import json, file

app = Application()


async def complex():
    return "Hello From a Coroutine"


@app.get("/hello/:id")
async def hello(req: Request, id: int, x: Annotated[str, Depends(complex)]):
    return json({"message": "Hello World!", "id": id, "x": x})


@app.get("/query")
async def query(req: Request, id: int | None = None):
    return json({"message": f"Hello World! {id}"})


@app.get("/read")
async def read(request: Request):
    return await file("README.md", request_headers=request.headers())


@app.middleware
async def middleware(request: Request, next: Callable):
    return await next(request)


if __name__ == "__main__":
    uvicorn.run(app, port=8000)
