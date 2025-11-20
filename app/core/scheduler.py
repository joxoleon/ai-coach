from datetime import date, timedelta
from typing import List, Dict, Any
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.loader import load_configs
from app.core.ai_selector import AISelector
from app.models.task import TodayTask
from app.models.history import TaskHistory
from app.models.daily_summary import DailySummary


settings = get_settings()
scheduler = BackgroundScheduler(timezone=pytz.timezone(settings.timezone))
ai_selector = AISelector()


def _serialize_history(rows: List[TaskHistory]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[TaskHistory]] = {}
    for r in rows:
        key = f"{r.group}:{r.name}"
        grouped.setdefault(key, []).append(r)

    payload: List[Dict[str, Any]] = []
    today = date.today()
    for records in grouped.values():
        records.sort(key=lambda x: x.timestamp, reverse=True)
        last_completed = next((r for r in records if r.completed), None)
        days_since_last_solved = (today - last_completed.date).days if last_completed else None

        # streak counted from most recent backwards until a non-completion
        streak = 0
        for r in records:
            if r.completed:
                streak += 1
            else:
                break

        difficulties = [r.difficulty for r in records if r.difficulty is not None]
        avg_difficulty = sum(difficulties) / len(difficulties) if difficulties else None
        solved_today = any(r.date == today and r.completed for r in records)

        sample = records[0]
        payload.append(
            {
                "name": sample.name,
                "group": sample.group,
                "last_seen": str(sample.date),
                "days_since_last_solved": days_since_last_solved,
                "streak": streak,
                "average_difficulty": avg_difficulty,
                "solved_today": solved_today,
                "difficulty_samples": difficulties,
                "total_sessions": len(records),
            }
        )
    return payload


def _serialize_today_tasks(rows: List[TodayTask]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for r in rows:
        payload.append(
            {
                "name": r.name,
                "group": r.group,
                "url": r.url,
                "reason": (r.extra or {}).get("reason"),
                "metadata": (r.extra or {}).get("metadata") or {},
            }
        )
    return payload


def generate_daily_tasks(session: Session) -> List[TodayTask]:
    groups = load_configs()
    history_window_start = date.today() - timedelta(days=settings.task_sample_days)
    history_rows = (
        session.query(TaskHistory)
        .filter(TaskHistory.date >= history_window_start)
        .order_by(TaskHistory.timestamp.desc())
        .all()
    )
    recent_today = (
        session.query(TodayTask)
        .filter(TodayTask.date >= history_window_start)
        .order_by(TodayTask.date.desc())
        .all()
    )

    plan, summary_notes, raw_ai = ai_selector.generate(
        groups,
        _serialize_history(history_rows),
        _serialize_today_tasks(recent_today),
        session,
    )

    session.query(TodayTask).filter(TodayTask.date == date.today()).delete()
    session.query(DailySummary).filter(DailySummary.date == date.today()).delete()

    created: List[TodayTask] = []
    for item in plan:
        metadata = item.get("metadata") or {}
        extra = {
            "reason": item.get("reason"),
            "metadata": metadata,
            "action": metadata.get("action"),
            "difficulty_estimate": item.get("difficulty_estimate"),
        }
        task = TodayTask(
            date=date.today(),
            name=item.get("name"),
            group=item.get("group"),
            url=item.get("url"),
            extra=extra,
        )
        session.add(task)
        created.append(task)

    session.add(
        DailySummary(
            date=date.today(),
            summary_text=summary_notes,
            raw_ai_response=raw_ai,
        )
    )

    session.commit()
    return created


def start_scheduler(get_session_callable):
    if scheduler.running:
        return

    def job_wrapper():
        session = get_session_callable()
        try:
            generate_daily_tasks(session)
        finally:
            session.close()

    trigger = CronTrigger(hour=0, minute=5)
    scheduler.add_job(job_wrapper, trigger=trigger, name="daily-task-generation", replace_existing=True)
    scheduler.start()
