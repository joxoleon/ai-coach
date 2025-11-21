from datetime import date, timedelta
from typing import List, Dict, Any, Tuple
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.loader import load_configs
from app.services.selector import select_with_fallback
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
                "module_id": getattr(sample, "module_id", None),
                "task_type": getattr(sample, "task_type", None),
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
                "module_id": getattr(r, "module_id", None),
                "name": r.name,
                "group": r.group,
                "url": r.url,
                "reason": (r.extra or {}).get("reason"),
                "metadata": (r.extra or {}).get("metadata") or {},
            }
        )
    return payload


def generate_module_tasks(
    session: Session,
    module_id: str,
    module_config: List[Dict[str, Any]],
    history_window_days: int,
) -> Tuple[List[Dict[str, Any]], str, str]:
    today = date.today()
    history_window_start = today - timedelta(days=history_window_days)
    history_rows = (
        session.query(TaskHistory)
        .filter(
            TaskHistory.date >= history_window_start,
            TaskHistory.module_id == module_id,
        )
        .order_by(TaskHistory.timestamp.desc())
        .all()
    )
    history_snippet = _serialize_history(history_rows)

    try:
        tasks, summary_notes, raw_ai = ai_selector.generate_for_module(
            module_id,
            module_config,
            history_snippet,
        )
        return tasks, summary_notes, raw_ai
    except Exception:
        fallback_tasks = select_with_fallback(session, module_config)
        return fallback_tasks, "Fallback selector used (AI disabled or unavailable).", "{}"


def generate_daily_tasks(session: Session) -> List[TodayTask]:
    loaded_configs = load_configs()
    module_configs = getattr(loaded_configs, "modules", {}) if loaded_configs is not None else {}
    today = date.today()

    session.query(TodayTask).filter(TodayTask.date == today).delete()
    session.query(DailySummary).filter(DailySummary.date == today).delete()

    created: List[TodayTask] = []
    for module_id, module_config in module_configs.items():
        tasks, summary_notes, raw_ai = generate_module_tasks(
            session,
            module_id,
            module_config,
            settings.task_sample_days,
        )

        for item in tasks:
            metadata = item.get("metadata") or {}
            task_type = item.get("task_type") or "todo"
            extra = {
                "reason": item.get("reason"),
                "metadata": metadata,
                "action": metadata.get("action"),
                "difficulty_estimate": item.get("difficulty_estimate"),
            }
            task = TodayTask(
                date=today,
                module_id=module_id,
                name=item.get("name"),
                group=item.get("group"),
                task_type=task_type,
                problem_text=item.get("problem_text"),
                code_template=item.get("code_template"),
                log=item.get("log"),
                url=item.get("url"),
                extra=extra,
            )
            session.add(task)
            created.append(task)

        session.add(
            DailySummary(
                date=today,
                module_id=module_id,
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
