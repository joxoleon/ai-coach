from datetime import date
import json
from typing import Any, Dict, List, Tuple

from app.core.config import get_settings
from app.services.prompt_loader import load_prompt_templates
from app.services.selector import select_with_fallback

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYSTEM_PROMPT = (
    "You are an adaptive scheduler for daily practice tasks. Return strictly valid JSON following the schema."
)
SCHEMA_SPEC = """
Required JSON schema:
{
    "date": "YYYY-MM-DD",
    "tasks": [
        {
            "name": "...",
            "group": "...",
            "importance": <optional>,
            "difficulty_estimate": <optional 1-5>,
            "reason": "...",
            "url": "... or null",
            "metadata": {... arbitrary additional data ...}
        }
    ],
    "summary_notes": "explanation of the reasoning and analysis (not a task)"
}
Reply with only JSON.
"""


class AISelector:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if OpenAI else None

    def _build_system_prompt(self) -> str:
        prompt_bundle = load_prompt_templates()
        combined = prompt_bundle or SYSTEM_PROMPT
        return combined + "\n\n" + SCHEMA_SPEC

    def _build_user_payload(
        self,
        groups: List[Dict[str, Any]],
        history_snippet: List[Dict[str, Any]],
        recent_tasks: List[Dict[str, Any]],
    ) -> str:
        payload = {
            "today_date": str(date.today()),
            "task_groups": groups,
            "recent_history": history_snippet,
            "recent_today_tasks": recent_tasks,
            "performance_window_days": self.settings.task_sample_days,
            "user_settings": {
                "daily_time_budget_minutes": self.settings.time_budget,
                "task_limits": self.settings.task_limits,
                "avoid_repetition_days": self.settings.avoid_days,
                "difficulty_scale_definition": "1=very easy, 5=very hard",
                "timezone": self.settings.timezone,
                "max_items_total": self.settings.max_items,
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def _validate_shape(self, data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        if not isinstance(data, dict):
            raise ValueError("AI response must be an object")

        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("AI response missing tasks array")

        cleaned: List[Dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            name = task.get("name")
            group = task.get("group")
            if not name or not group:
                continue
            cleaned.append(
                {
                    "name": name,
                    "group": group,
                    "importance": task.get("importance"),
                    "difficulty_estimate": task.get("difficulty_estimate"),
                    "reason": task.get("reason"),
                    "url": task.get("url"),
                    "metadata": task.get("metadata") or {},
                }
            )

        if not cleaned:
            raise ValueError("AI response had no valid tasks")

        summary_notes = data.get("summary_notes") or ""
        if not isinstance(summary_notes, str):
            summary_notes = str(summary_notes)

        return cleaned, summary_notes

    def _call_model(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("OpenAI client not configured")
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)

    def _request_with_retries(self, messages: List[Dict[str, str]], retries: int = 2) -> Dict[str, Any]:
        last_error: Exception | None = None
        working_messages = list(messages)
        for _attempt in range(retries + 1):
            try:
                return self._call_model(working_messages)
            except Exception as exc:  # pragma: no cover - runtime guard
                last_error = exc
                correction_note = {
                    "role": "user",
                    "content": "Your last reply was invalid JSON. Reply again with ONLY valid JSON conforming to the schema.",
                }
                working_messages.append(correction_note)
        if last_error:
            raise last_error
        raise RuntimeError("AI request failed with unknown error.")

    def generate(
        self,
        groups: List[Dict[str, Any]],
        history_snippet: List[Dict[str, Any]],
        recent_tasks: List[Dict[str, Any]],
        session,
    ) -> Tuple[List[Dict[str, Any]], str, str]:
        if not self.settings.use_ai or not self.client:
            tasks = select_with_fallback(session, groups)
            return tasks, "Fallback selector used (AI disabled or unavailable).", "{}"

        system_prompt = self._build_system_prompt()
        user_content = self._build_user_payload(groups, history_snippet, recent_tasks)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            data = self._request_with_retries(messages)
            tasks, summary_notes = self._validate_shape(data)
            return tasks, summary_notes, json.dumps(data)
        except Exception:
            tasks = select_with_fallback(session, groups)
            return tasks, "Fallback selector used after AI failure.", "{}"
