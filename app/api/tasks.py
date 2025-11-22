from datetime import date, timedelta, datetime
from collections import defaultdict
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.task import TodayTask
from app.models.history import TaskHistory

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class DonePayload(BaseModel):
    task_id: int | None = None
    name: str
    group: str
    difficulty: int | None = Field(default=None, ge=1, le=5)
    log: str | None = None


class FeedbackPayload(BaseModel):
    task_id: int | None = None
    name: str
    group: str
    difficulty: int = Field(ge=1, le=5)
    log: str | None = None


class LogPayload(BaseModel):
    log: str | None = None


class CompletePayload(BaseModel):
    difficulty: int | None = Field(default=None, ge=1, le=5)
    log: str | None = None


class NotesPayload(BaseModel):
    notes: str | None = None


def _find_today_task(db: Session, task_id: int | None, name: str, group: str) -> TodayTask | None:
    if task_id:
        entry = db.query(TodayTask).filter(TodayTask.id == task_id).first()
        if entry:
            return entry
    return (
        db.query(TodayTask)
        .filter(
            TodayTask.date == date.today(),
            TodayTask.name == name,
            TodayTask.group == group,
        )
        .first()
    )


@router.get("/today")
def get_today(db: Session = Depends(get_db)) -> Dict[str, Any]:
    today = date.today()
    tasks = db.query(TodayTask).filter(TodayTask.date == today).all()
    payload = [
        {
            "module_id": t.module_id,
            "id": t.id,
            "name": t.name,
            "group": t.group,
            "task_type": t.task_type,
            "problem_text": t.problem_text,
            "code_template": t.code_template,
            "log": t.log,
            "url": t.url,
            "reason": (t.extra or {}).get("reason"),
            "metadata": (t.extra or {}).get("metadata") or {},
            "action": (t.extra or {}).get("action"),
            "difficulty_estimate": (t.extra or {}).get("difficulty_estimate"),
        }
        for t in tasks
    ]
    return {"date": str(today), "tasks": payload}


@router.get("/tasks/module/{module_id}")
def get_tasks_for_module(module_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    today = date.today()
    tasks = (
        db.query(TodayTask)
        .filter(TodayTask.date == today)
        .filter(TodayTask.module_id == module_id)
        .all()
    )
    payload = [
        {
            "module_id": t.module_id,
            "id": t.id,
            "name": t.name,
            "group": t.group,
            "task_type": t.task_type,
            "problem_text": t.problem_text,
            "code_template": t.code_template,
            "log": t.log,
            "url": t.url,
            "reason": (t.extra or {}).get("reason"),
            "metadata": (t.extra or {}).get("metadata") or {},
            "action": (t.extra or {}).get("action"),
            "difficulty_estimate": (t.extra or {}).get("difficulty_estimate"),
        }
        for t in tasks
    ]
    return {"date": str(today), "tasks": payload}


@router.post("/done")
def mark_done(payload: DonePayload, db: Session = Depends(get_db)):
    today_entry = _find_today_task(db, payload.task_id, payload.name, payload.group)
    module_id = today_entry.module_id if today_entry else "unknown"
    task_type = today_entry.task_type if today_entry else "todo"
    history = TaskHistory(
        date=date.today(),
        module_id=module_id,
        name=payload.name,
        group=payload.group,
        task_type=task_type,
        problem_text=today_entry.problem_text if today_entry else None,
        todo_text=today_entry.todo_text if today_entry else None,
        code_template=today_entry.code_template if today_entry else None,
        notes=today_entry.notes if today_entry else None,
        log=payload.log if payload.log is not None else (today_entry.log if today_entry else None),
        completed=True,
        difficulty=payload.difficulty,
        timestamp=datetime.utcnow(),
    )
    db.add(history)
    db.commit()
    return {"status": "ok", "task_id": payload.task_id or (today_entry.id if today_entry else None)}


@router.post("/feedback")
def feedback(payload: FeedbackPayload, db: Session = Depends(get_db)):
    today_entry = _find_today_task(db, payload.task_id, payload.name, payload.group)
    module_id = today_entry.module_id if today_entry else "unknown"
    task_type = today_entry.task_type if today_entry else "todo"
    history = TaskHistory(
        date=date.today(),
        module_id=module_id,
        name=payload.name,
        group=payload.group,
        task_type=task_type,
        problem_text=today_entry.problem_text if today_entry else None,
        todo_text=today_entry.todo_text if today_entry else None,
        code_template=today_entry.code_template if today_entry else None,
        notes=today_entry.notes if today_entry else None,
        log=payload.log if payload.log is not None else (today_entry.log if today_entry else None),
        completed=False,
        difficulty=payload.difficulty,
        timestamp=datetime.utcnow(),
    )
    db.add(history)
    db.commit()
    return {"status": "recorded"}


@router.get("/history")
def history(days: int = 7, db: Session = Depends(get_db)):
    cutoff = date.today() - timedelta(days=days)
    rows = (
        db.query(TaskHistory)
        .filter(TaskHistory.date >= cutoff)
        .order_by(TaskHistory.date.desc())
        .all()
    )
    return [
        {
            "date": str(r.date),
            "name": r.name,
            "group": r.group,
            "completed": r.completed,
            "difficulty": r.difficulty,
            "module_id": r.module_id,
            "task_type": r.task_type,
            "log": r.log,
        }
        for r in rows
    ]


@router.get("/tasks/module/{module_id}/fragment", response_class=HTMLResponse)
def module_tasks_fragment(module_id: str, request: Request, db: Session = Depends(get_db)):
    today = date.today()
    tasks = (
        db.query(TodayTask)
        .filter(TodayTask.date == today)
        .filter(TodayTask.module_id == module_id)
        .all()
    )
    return templates.TemplateResponse(
        "components/module_task_list.html",
        {
            "request": request,
            "items": tasks,
            "module_id": module_id,
        },
    )


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(request: Request, task_id: int, db: Session = Depends(get_db)):
    task = db.query(TodayTask).filter(TodayTask.id == task_id).first()
    source = "today"
    if not task:
        task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
        source = "history"
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    template_name = "tasks/coding_detail.html" if task.task_type == "coding" else "tasks/todo_detail.html"
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "task": task,
            "module_id": task.module_id,
            "title": task.name,
            "problem_text": task.problem_text,
            "code_template": task.code_template,
            "log": task.log,
            "source": source,
        },
    )


@router.post("/tasks/{task_id}/log")
def update_task_log(task_id: int, payload: LogPayload, db: Session = Depends(get_db)):
    task = db.query(TodayTask).filter(TodayTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.log = payload.log
    db.commit()
    return {"status": "saved", "task_id": task_id}


@router.patch("/api/tasks/{task_id}/notes")
def update_task_notes(task_id: int, payload: NotesPayload, db: Session = Depends(get_db)):
    task = db.query(TodayTask).filter(TodayTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.notes = payload.notes
    db.commit()
    return {"status": "saved", "task_id": task_id, "notes": task.notes}


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, payload: CompletePayload, db: Session = Depends(get_db)):
    task = db.query(TodayTask).filter(TodayTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    history = TaskHistory(
        date=date.today(),
        module_id=task.module_id,
        name=task.name,
        group=task.group,
        task_type=task.task_type,
        problem_text=task.problem_text,
        todo_text=task.todo_text,
        code_template=task.code_template,
        notes=task.notes,
        log=payload.log if payload.log is not None else task.log,
        completed=True,
        difficulty=payload.difficulty,
        timestamp=datetime.utcnow(),
    )
    db.add(history)
    db.delete(task)
    db.commit()
    return {"status": "completed", "task_id": task_id}
@router.get("/api/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    task = db.query(TodayTask).filter(TodayTask.id == task_id).first()
    source = "today"
    if not task:
        task = db.query(TaskHistory).filter(TaskHistory.id == task_id).first()
        source = "history"
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    def serialize(t):
        return {
            "id": t.id,
            "date": str(t.date),
            "module_id": t.module_id,
            "name": t.name,
            "group": t.group,
            "task_type": getattr(t, "task_type", "todo"),
            "problem_text": getattr(t, "problem_text", None),
            "todo_text": getattr(t, "todo_text", None),
            "code_template": getattr(t, "code_template", None),
            "notes": getattr(t, "notes", None),
            "log": getattr(t, "log", None),
            "url": t.url,
            "extra": t.extra,
            "reason": (t.extra or {}).get("reason") if t.extra else None,
            "metadata": (t.extra or {}).get("metadata") if t.extra else None,
            "difficulty_estimate": (t.extra or {}).get("difficulty_estimate") if t.extra else None,
            "importance": (t.extra or {}).get("importance") if t.extra else None,
            "source": source,
        }

    return serialize(task)
