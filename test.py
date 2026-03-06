from sevro.app import Application
from sevro.request import Request
from sevro.responses.file import FileResponse

app = Application()


@app.get("/hello/:id")
async def hello(req: Request, id: int):
    return {"message": f"Hello World! {id}"}


@app.get("/read")
async def read():
    return FileResponse("README.md")
