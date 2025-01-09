from fastapi import Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from core import get_all_downloads


app = FastAPI()

app.mount('/css', StaticFiles(directory='css'), name='css')

templates = Jinja2Templates(directory='templates')

@app.get("/", response_class=HTMLResponse)
def read_users(request: Request):
    downloads = get_all_downloads()
    return templates.TemplateResponse("admin.html", {"request": request, "downloads": downloads})
