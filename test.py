import uvicorn

from sevro import Application, Request
from sevro.exception import HTTPException
from sevro.responses import text
from sevro.routes import Routes

routes = Routes()
sub = Routes("/user")

@routes.get("/")
async def index():
    return text("hello")

@routes.get("/hello")
async def hello():
    return "hello!"

@sub.get("/me")
async def me():
    return "me"

@sub.post("/me")
async def me_post():
    return "posted"

routes.mount(sub, "/api/v1")


app = Application(routes)

@app.error_handler(HTTPException)
async def handle_http(request: Request, err: HTTPException):
    return text(str(err), status=err.status_code)



if __name__ == "__main__":
    uvicorn.run(app, port=8000)
