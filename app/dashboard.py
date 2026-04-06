from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.stats import get_aggregate_stats, get_recent_logs

app = FastAPI(title="MultiProxy Dashboard")
templates = Jinja2Templates(directory="app/templates")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html"
    )

@app.get("/api/stats")
async def api_stats():
    return get_aggregate_stats()

@app.get("/api/logs")
async def api_logs(limit: int = 50, offset: int = 0):
    return get_recent_logs(limit=limit, offset=offset)

