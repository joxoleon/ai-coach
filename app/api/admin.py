from datetime import date
import html
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.scheduler import generate_daily_tasks
from app.models.task import TodayTask
from app.models.history import TaskHistory
from app.models.daily_summary import DailySummary

router = APIRouter()


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)):
    tasks = generate_daily_tasks(db)
    return {"status": "refreshed", "count": len(tasks)}


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
