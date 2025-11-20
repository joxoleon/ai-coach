from datetime import date, datetime, timedelta
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


settings = get_settings()
scheduler = BackgroundScheduler(timezone=pytz.timezone(settings.timezone))
ai_selector = AISelector()


def _serialize_history(rows: List[Any]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for r in rows:
        item = {
            "date": str(getattr(r, "date", "")),
            "name": getattr(r, "name", ""),
            "group": getattr(r, "group", ""),
        }
        if hasattr(r, "completed"):
            item["completed"] = getattr(r, "completed")
        if hasattr(r, "difficulty"):
            item["difficulty"] = getattr(r, "difficulty")
        if hasattr(r, "url"):
            item["url"] = getattr(r, "url")
        payload.append(item)
    return payload


def generate_daily_tasks(session: Session) -> List[TodayTask]:
    groups = load_configs()
    history_window_start = date.today() - timedelta(days=settings.task_sample_days)
    history_rows = (
        session.query(TaskHistory)
        .filter(TaskHistory.date >= history_window_start)
        .order_by(TaskHistory.date.desc())
        .all()
    )
    recent_today = (
        session.query(TodayTask)
        .filter(TodayTask.date >= history_window_start)
        .order_by(TodayTask.date.desc())
        .all()
    )

    plan = ai_selector.generate(groups, _serialize_history(history_rows), _serialize_history(recent_today), session)

    # wipe existing tasks for today
    session.query(TodayTask).filter(TodayTask.date == date.today()).delete()

    created: List[TodayTask] = []
    for item in plan:
        task = TodayTask(
            date=date.today(),
            name=item.get("name"),
            group=item.get("group"),
            url=item.get("url"),
            extra={"reason": item.get("reason")},
        )
        session.add(task)
        created.append(task)

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
