from datetime import date, timedelta, datetime
from collections import defaultdict
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.task import TodayTask
from app.models.history import TaskHistory

router = APIRouter()


class DonePayload(BaseModel):
    task_id: int | None = None
    name: str
    group: str
    difficulty: int | None = Field(default=None, ge=1, le=5)


class FeedbackPayload(BaseModel):
    task_id: int | None = None
    name: str
    group: str
    difficulty: int = Field(ge=1, le=5)


@router.get("/today")
def get_today(db: Session = Depends(get_db)) -> Dict[str, Any]:
    today = date.today()
    tasks = db.query(TodayTask).filter(TodayTask.date == today).all()
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in tasks:
        grouped[t.group].append(
            {
                "id": t.id,
                "name": t.name,
                "url": t.url,
                "reason": (t.extra or {}).get("reason"),
                "metadata": (t.extra or {}).get("metadata") or {},
                "action": (t.extra or {}).get("action"),
                "difficulty_estimate": (t.extra or {}).get("difficulty_estimate"),
            }
        )
    return {"date": str(today), "tasks": grouped}


@router.post("/done")
def mark_done(payload: DonePayload, db: Session = Depends(get_db)):
    today_entry = None
    if payload.task_id:
        today_entry = db.query(TodayTask).filter(TodayTask.id == payload.task_id).first()
    history = TaskHistory(
        date=date.today(),
        name=payload.name,
        group=payload.group,
        completed=True,
        difficulty=payload.difficulty,
        timestamp=datetime.utcnow(),
    )
    db.add(history)
    db.commit()
    return {"status": "ok", "task_id": payload.task_id or (today_entry.id if today_entry else None)}


@router.post("/feedback")
def feedback(payload: FeedbackPayload, db: Session = Depends(get_db)):
    history = TaskHistory(
        date=date.today(),
        name=payload.name,
        group=payload.group,
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
        }
        for r in rows
    ]
