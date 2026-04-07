from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.stats import get_aggregate_stats, get_recent_logs
import datetime

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

@app.get("/api/stats/html", response_class=HTMLResponse)
async def api_stats_html(request: Request, period: str = "all"):
    hours = None
    if period == "hour":
        hours = 1
    elif period == "day":
        hours = 24
    elif period == "month":
        hours = 24 * 30
        
    stats = get_aggregate_stats(hours=hours)
    return templates.TemplateResponse(
        request=request, name="stats.html", context={"stats": stats, "period": period}
    )

@app.get("/api/logs/html", response_class=HTMLResponse)
async def api_logs_html(request: Request, limit: int = 10, offset: int = 0):
    logs = get_recent_logs(limit=limit, offset=offset)
    for log in logs:
        log["timestamp_formatted"] = datetime.datetime.fromtimestamp(log["timestamp"]).strftime('%Y-%m-%d %H:%M:%S')
    return templates.TemplateResponse(
        request=request, name="logs.html", context={"logs": logs, "limit": limit, "offset": offset}
    )

