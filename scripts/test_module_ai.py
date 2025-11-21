import json
from datetime import date, timedelta
from pprint import pprint

from app.core.config import get_settings
from app.services.loader import load_configs
from app.core.ai_selector import AISelector
from app.core.database import SessionLocal
from app.models.history import TaskHistory


def get_session():
    return SessionLocal()


def main():
    MODULE_ID = "dsa_fundamentals"
    print("Testing AI generation for module:", MODULE_ID)

    settings = get_settings()
    loaded = load_configs()
    module_configs = getattr(loaded, "modules", {}) if loaded is not None else {}
    module_config = module_configs.get(MODULE_ID)
    if not module_config:
        raise SystemExit(f"Module '{MODULE_ID}' not found in configs.")

    history_window_start = date.today() - timedelta(days=settings.task_sample_days)
    session = get_session()
    try:
        history_rows = (
            session.query(TaskHistory)
            .filter(TaskHistory.module_id == MODULE_ID)
            .filter(TaskHistory.date >= history_window_start)
            .order_by(TaskHistory.timestamp.desc())
            .all()
        )
    finally:
        session.close()

    history_snippet = [
        {
            "name": r.name,
            "group": r.group,
            "difficulty": r.difficulty,
            "completed": r.completed,
            "timestamp": str(r.timestamp),
        }
        for r in history_rows
    ]

    ai = AISelector()
    tasks, summary_notes, raw_ai = ai.generate_for_module(
        module_id=MODULE_ID,
        module_config=module_config,
        history_snippet=history_snippet,
        settings={
            "daily_time_budget_minutes": settings.time_budget,
            "task_limits": settings.task_limits,
            "avoid_repetition_days": settings.avoid_days,
            "difficulty_scale_definition": "1=very easy, 5=very hard",
            "timezone": settings.timezone,
            "max_items_total": settings.max_items,
        },
    )

    print("\n=== RAW AI JSON ===")
    print(raw_ai)

    print("\n=== PARSED TASKS ===")
    pprint(tasks)

    print("\n=== SUMMARY NOTES ===")
    print(summary_notes)

    print("\n=== TASK FORMAT CHECK ===")
    for t in tasks:
        if t.get("task_type") == "coding":
            has_code = bool(t.get("code_template"))
            has_desc = bool(t.get("problem_text"))
            print(f"- {t.get('name')}: coding template OK? {has_code} | description OK? {has_desc}")
        else:
            has_text = bool(t.get("problem_text") or t.get("todo_text"))
            print(f"- {t.get('name')}: todo text present? {has_text}")


if __name__ == "__main__":
    main()
