import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.history import TaskHistory


TaskPlan = Dict[str, Any]


class FallbackSelector:
    def __init__(self, session: Session):
        self.session = session

    def _history_lookup(self) -> Dict[str, List[TaskHistory]]:
        records: Dict[str, List[TaskHistory]] = defaultdict(list)
        rows = self.session.query(TaskHistory).order_by(TaskHistory.timestamp.desc()).all()
        for row in rows:
            key = f"{row.group}:{row.name}"
            records[key].append(row)
        return records

    def _score_item(self, item: Dict[str, Any], group: str, history_map: Dict[str, List[TaskHistory]]) -> float:
        key = f"{group}:{item['name']}"
        records = history_map.get(key, [])
        last_seen_days = 999
        success_streak = 0
        difficulty_bias = 0.0

        if records:
            delta = date.today() - records[0].date
            last_seen_days = max(delta.days, 1)
            # compute streak of completions
            for record in records:
                if record.completed:
                    success_streak += 1
                else:
                    break
            difficulties = [r.difficulty for r in records if r.difficulty]
            if difficulties:
                avg_diff = sum(difficulties) / len(difficulties)
                difficulty_bias = (avg_diff - 3) * 0.5

        importance = item.get("importance", 1)
        score = importance * 2 + (1 / last_seen_days) - success_streak + difficulty_bias
        return score

    def generate(self, groups: List[Dict[str, Any]]) -> List[TaskPlan]:
        history_map = self._history_lookup()
        plan: List[TaskPlan] = []

        pick_counts = {
            "fundamentals": 3,
            "leetcode": 1,
            "habits": 1,
            "study": 1,
        }

        for group_data in groups:
            group_name = group_data.get("group", "Unknown")
            items = group_data.get("items", [])
            if not items:
                continue
            key = group_name.lower()
            if "fundamental" in key:
                target = pick_counts.get("fundamentals", 2)
            elif "leetcode" in key:
                target = pick_counts.get("leetcode", 1)
            elif "habit" in key:
                target = pick_counts.get("habits", 1)
            elif "study" in key:
                target = pick_counts.get("study", 1)
            else:
                target = pick_counts.get(key, 1)
            scored = [
                (self._score_item(item, group_name, history_map), item)
                for item in items
            ]
            scored.sort(key=lambda v: v[0], reverse=True)

            chosen = scored[:target]
            for _, item in chosen:
                plan.append({
                    "name": item.get("name"),
                    "group": group_name,
                    "url": item.get("url"),
                    "reason": "Fallback selector based on recency/importance",
                })

            # slight rotation if fundamentals has more than threshold
            if key == "fundamentals" and len(plan) < 2:
                extra = random.choice(items)
                plan.append({
                    "name": extra.get("name"),
                    "group": group_name,
                    "url": extra.get("url"),
                    "reason": "Added for rotation",
                })
        return plan


def select_with_fallback(session: Session, groups: List[Dict[str, Any]]) -> List[TaskPlan]:
    return FallbackSelector(session).generate(groups)
