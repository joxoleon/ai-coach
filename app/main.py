from datetime import date
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.services.avatar_picker import pick_avatar_for_day, pick_quote_for_avatar, pick_random_avatar
from app.services.loader import load_configs

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
    grouped: Dict[str, list[TodayTask]] = {}
    for t in tasks:
        grouped.setdefault(t.group, []).append(t)
    avatar = pick_random_avatar()
    if avatar:
        avatar_quote = pick_quote_for_avatar(avatar)
        if avatar_quote:
            avatar = {**avatar, "quote": avatar_quote}
    tab_param = request.query_params.get("tab", "today")
    configs = load_configs()
    tabs = ["today"] + list(configs.keys())
    active_tab = tab_param if tab_param in tabs else "today"

    # Map tasks to YAML file tabs by matching group names inside each config file
    tasks_by_tab: Dict[str, Dict[str, list[TodayTask]]] = {}
    for cfg_name, entries in configs.items():
        file_mapping: Dict[str, list[TodayTask]] = {}
        for entry in entries:
            gname = entry.get("group")
            if gname and gname in grouped:
                file_mapping[gname] = grouped[gname]
        tasks_by_tab[cfg_name] = file_mapping

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "tasks_all": grouped,
            "tasks": tasks_by_tab,
            "date": today,
            "avatar": avatar,
            "tabs": tabs,
            "active_tab": active_tab,
            "configs": configs,
        },
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
