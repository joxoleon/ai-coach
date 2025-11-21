from datetime import date
import html
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.scheduler import generate_daily_tasks, generate_module_tasks
from app.models.task import TodayTask
from app.models.history import TaskHistory
from app.models.daily_summary import DailySummary
from app.services.loader import load_configs
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)):
    tasks = generate_daily_tasks(db)
    return {"status": "refreshed", "count": len(tasks)}


@router.post("/refresh/module/{module_id}", response_class=HTMLResponse)
def refresh_module(module_id: str, request: Request, db: Session = Depends(get_db)):
    loaded_configs = load_configs()
    module_configs = getattr(loaded_configs, "modules", {}) if loaded_configs is not None else {}
    module_config = module_configs.get(module_id)
    if not module_config:
        return HTMLResponse(
            content=f"<p class='text-slate-400 text-sm'>Module '{module_id}' not found.</p>",
            status_code=404,
        )

    # delete existing tasks/summary for this module today
    db.query(TodayTask).filter(TodayTask.date == date.today(), TodayTask.module_id == module_id).delete()
    db.query(DailySummary).filter(DailySummary.date == date.today(), DailySummary.module_id == module_id).delete()

    tasks, summary_notes, raw_ai = generate_module_tasks(db, module_id, module_config, settings.task_sample_days)

    created = 0
    for item in tasks:
        metadata = item.get("metadata") or {}
        extra = {
            "reason": item.get("reason"),
            "metadata": metadata,
            "action": metadata.get("action"),
            "difficulty_estimate": item.get("difficulty_estimate"),
        }
        task = TodayTask(
            date=date.today(),
            module_id=module_id,
            name=item.get("name"),
            group=item.get("group"),
            task_type=item.get("task_type") or "todo",
            problem_text=item.get("problem_text"),
            code_template=item.get("code_template"),
            log=item.get("log"),
            url=item.get("url"),
            extra=extra,
        )
        db.add(task)
        created += 1

    db.add(
        DailySummary(
            date=date.today(),
            module_id=module_id,
            summary_text=summary_notes,
            raw_ai_response=raw_ai,
        )
    )
    db.commit()

    refreshed = (
        db.query(TodayTask)
        .filter(TodayTask.date == date.today(), TodayTask.module_id == module_id)
        .all()
    )

    return templates.TemplateResponse(
        "components/module_task_list.html",
        {"request": request, "items": refreshed, "module_id": module_id},
    )


@router.get("/admin/plan", response_class=HTMLResponse)
def plan(db: Session = Depends(get_db)):
    tasks = db.query(TodayTask).filter(TodayTask.date == date.today()).all()
    if not tasks:
        return "<p class='text-slate-500'>No plan generated yet.</p>"
    lines = []
    for t in tasks:
        url = (
            f"<a href='{t.url}' class='text-sky-300' target='_blank' rel='noopener'>link</a>"
            if t.url
            else ""
        )
        reason = (t.extra or {}).get("reason") or ""
        lines.append(
            f"<div class='mb-2'><div class='font-medium'>{t.group}: {t.name} {url}</div><div class='text-slate-400 text-xs'>{reason}</div></div>"
        )
    return "".join(lines)


@router.get("/admin/history", response_class=HTMLResponse)
def admin_history(db: Session = Depends(get_db)):
    cutoff = date.today() - timedelta(days=7)
    rows = (
        db.query(TaskHistory)
        .filter(TaskHistory.date >= cutoff)
        .order_by(TaskHistory.date.desc(), TaskHistory.timestamp.desc())
        .all()
    )
    if not rows:
        return "<p class='text-slate-500'>No history yet.</p>"
    items = [
        f"<div class='grid grid-cols-5 gap-2 text-xs border-b border-slate-800 py-1'><span>{r.date}</span><span class='col-span-2'>{r.name}</span><span>{r.group}</span><span>{'done' if r.completed else 'pending'} / {r.difficulty or ''}</span></div>"
        for r in rows
    ]
    header = "<div class='grid grid-cols-5 gap-2 text-xs text-slate-400 uppercase tracking-wide pb-1 border-b border-slate-800'><span>Date</span><span class='col-span-2'>Name</span><span>Group</span><span>Status</span></div>"
    return header + "".join(items)


@router.get("/admin/summary", response_class=HTMLResponse)
def admin_summary(db: Session = Depends(get_db)):
    summary = (
        db.query(DailySummary)
        .filter(DailySummary.date == date.today())
        .order_by(DailySummary.id.desc())
        .first()
    )
    if not summary:
        return "<p class='text-slate-500'>No summary generated yet.</p>"
    raw = html.escape(summary.raw_ai_response or "{}")
    text = html.escape(summary.summary_text or "—")
    return (
        f"<div class='space-y-2'><p class='text-sm text-slate-200'>Summary: {text}</p>"
        f"<pre class='bg-slate-950 border border-slate-800 rounded p-2 text-[11px] overflow-auto'>{raw}</pre></div>"
    )
