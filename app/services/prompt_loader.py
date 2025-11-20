from pathlib import Path
from typing import List

PROMPT_DIR = Path(__file__).resolve().parents[2] / "configs" / "prompts"


def load_prompt_templates(base_dir: Path | None = None) -> str:
    directory = base_dir or PROMPT_DIR
    if not directory.exists():
        return ""

    parts: List[str] = []
    text_files = sorted(list(directory.glob("*.md")) + list(directory.glob("*.txt")))
    for file in text_files:
        try:
            parts.append(file.read_text(encoding="utf-8"))
        except OSError:
            continue

    examples_file = directory / "examples.json"
    if examples_file.exists():
        try:
            parts.append("Examples:\n" + examples_file.read_text(encoding="utf-8"))
        except OSError:
            pass

    return "\n\n".join(part.rstrip() for part in parts if part)
