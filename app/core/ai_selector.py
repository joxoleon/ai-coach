import json
from datetime import date
from typing import Any, Dict, List

from app.core.config import get_settings
from app.services.selector import select_with_fallback

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYSTEM_PROMPT = """
You are an adaptive scheduler for daily practice tasks.
Your job is to design a balanced, reasonable workload for the user for today.
Use the following inputs:
- Task groups and their items with importance.
- User’s performance history.
- Difficulty ratings.
- Last 14 days of tasks.
- Daily time budget: 45–60 minutes.

Return ONLY valid JSON with "date" and a "tasks" array.
Tasks should be varied, not repetitive, and must reflect weaknesses and importance.
Some tasks may be conversational ("Discuss DP Tabulation vs Memoization with AI"), physical ("Walk 10,000 steps"), or study-oriented ("Watch NeetCode DP-5 video").
"""


class AISelector:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if OpenAI else None

    def _format_prompt(
        self,
        groups: List[Dict[str, Any]],
        history_snippet: List[Dict[str, Any]],
        recent_tasks: List[Dict[str, Any]],
    ) -> str:
        payload = {
            "today": str(date.today()),
            "groups": groups,
            "recent_history": history_snippet,
            "recent_tasks": recent_tasks,
            "target_time_minutes": "45-60",
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _validate_shape(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(data, dict):
            raise ValueError("AI response must be an object")
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("AI response missing tasks array")
        cleaned = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            name = task.get("name")
            group = task.get("group")
            if not name or not group:
                continue
            cleaned.append({
                "name": name,
                "group": group,
                "url": task.get("url"),
                "reason": task.get("reason"),
            })
        if not cleaned:
            raise ValueError("AI response had no valid tasks")
        return cleaned

    def generate(
        self,
        groups: List[Dict[str, Any]],
        history_snippet: List[Dict[str, Any]],
        recent_tasks: List[Dict[str, Any]],
        session,
    ) -> List[Dict[str, Any]]:
        if not self.settings.use_ai or not self.client:
            return select_with_fallback(session, groups)

        prompt = self._format_prompt(groups, history_snippet, recent_tasks)

        try:
            response = self.client.responses.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = getattr(response, "output_text", None)
            if not content and hasattr(response, "output"):
                content = response.output[0].content[0].text  # type: ignore
            data = json.loads(content)
            return self._validate_shape(data)
        except Exception:
            # fall back to deterministic selector
            return select_with_fallback(session, groups)
