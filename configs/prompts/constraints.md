Constraints:
- Output strictly valid JSON that matches the provided schema.
- Do not invent groups not present in the input groups.
- tasks[].reason must concisely justify inclusion.
- tasks[].metadata may include tags like {"action": "ai_conversation" | "practice" | "external_link" | "movement"}.
- Avoid repeating the exact same task within the avoid_repetition_days window unless explicitly necessary.
- Include summary_notes explaining rationale and sequencing (not a task itself).
