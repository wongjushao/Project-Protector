# app/routers/dashboard_router.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/audit", response_class=HTMLResponse)
async def audit_dashboard(request: Request):
    """Serve the audit dashboard page"""
    return templates.TemplateResponse("audit_dashboard.html", {"request": request})
