from typing import Annotated

import uvicorn

from sevro.app import Application
from sevro.depends import Depends
from sevro.request import Request
from sevro.responses.file import FileResponse

app = Application()


async def complex():
    return "Jimmy"


@app.get("/hello/:id")
async def hello(req: Request, id: int, x: Annotated[str, Depends(complex)]):
    return {"message": f"Hello World! {id} {x}"}


@app.get("/query")
async def query(req: Request, id: int | None = None):
    return {"message": f"Hello World! {id}"}


@app.get("/read")
async def read():
    return FileResponse("README.md")


if __name__ == "__main__":
    uvicorn.run(app, port=8000)
