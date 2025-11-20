from datetime import date
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import tasks as tasks_router
from app.api import admin as admin_router
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.scheduler import start_scheduler, generate_daily_tasks, scheduler
from app.models.task import TodayTask
from app.models.daily_summary import DailySummary  # noqa: F401 - ensure table creation

app = FastAPI(title="Adaptive Daily Task Scheduler")
app.include_router(tasks_router.router)
app.include_router(admin_router.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    start_scheduler(SessionLocal)
    # ensure today has tasks
    session = SessionLocal()
    try:
        exists = session.query(TodayTask).filter(TodayTask.date == date.today()).first()
        if not exists:
            generate_daily_tasks(session)
    finally:
        session.close()


@app.on_event("shutdown")
def shutdown_event():
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db=Depends(get_db)):
    # reuse /today data for template
    today = date.today()
    tasks = db.query(TodayTask).filter(TodayTask.date == today).all()
    grouped = {}
    for t in tasks:
        grouped.setdefault(t.group, []).append(t)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "tasks": grouped, "date": today},
    )


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, db=Depends(get_db)):
    today = date.today()
    tasks = db.query(TodayTask).filter(TodayTask.date == today).all()
    history = []
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "tasks": tasks, "date": today, "history": history},
    )
