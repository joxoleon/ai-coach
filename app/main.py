from datetime import date
from typing import Dict, List
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.services.avatar_picker import pick_random_avatar, pick_quote_for_avatar
from app.services.loader import load_configs

from app.api import tasks as tasks_router
from app.api import admin as admin_router
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.scheduler import start_scheduler, generate_daily_tasks, scheduler
from app.models.task import TodayTask
from app.models.daily_summary import DailySummary  # noqa: F401 - ensure table creation
from app.models.history import TaskHistory

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
    module_tasks: Dict[str, List[TodayTask]] = {}
    for t in tasks:
        module_tasks.setdefault(t.module_id, []).append(t)

    avatar = pick_random_avatar()
    if avatar:
        avatar_quote = pick_quote_for_avatar(avatar)
        if avatar_quote:
            avatar = {**avatar, "quote": avatar_quote}

    loaded_configs = load_configs()
    configs = getattr(loaded_configs, "modules", {}) if loaded_configs is not None else {}
    tabs = ["today"] + sorted(configs.keys())
    module_labels = {mid: mid.replace("-", " ").replace("_", " ").title() for mid in configs.keys()}
    tab_param = request.query_params.get("tab", "today")
    active_tab = tab_param if tab_param in tabs else "today"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "module_tasks": module_tasks,
            "module_labels": module_labels,
            "configs": configs,
            "date": today,
            "avatar": avatar,
            "tabs": tabs,
            "active_tab": active_tab,
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


@app.get("/task/{task_id}", response_class=HTMLResponse)
def task_detail_page(task_id: int, request: Request, db=Depends(get_db)):
    task = db.query(TodayTask).filter(TodayTask.id == task_id).first()
    if not task:
        task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
    if not task:
        return HTMLResponse("Task not found", status_code=404)
    module_label = task.module_id.replace("-", " ").replace("_", " ").title()
    template_name = "tasks/coding_detail.html" if task.task_type == "coding" else "tasks/todo_detail.html"
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "task": task,
            "module_id": module_label,
            "title": task.name,
            "problem_text": task.problem_text or task.todo_text,
            "code_template": task.code_template,
            "log": task.log,
        },
    )
