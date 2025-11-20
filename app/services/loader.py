import glob
import yaml
from pathlib import Path
from typing import Any, Dict, List

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


def _validate_group(data: Dict[str, Any], path: Path) -> Dict[str, Any]:
    if "group" not in data or "items" not in data:
        raise ValueError(f"Config {path.name} missing required keys")
    if not isinstance(data["items"], list):
        raise ValueError(f"Config {path.name} items must be a list")
    for item in data["items"]:
        if "name" not in item or "importance" not in item:
            raise ValueError(f"Item in {path.name} missing name or importance")
    return data


def load_configs(config_dir: Path | None = None) -> List[Dict[str, Any]]:
    base = config_dir or CONFIG_DIR
    groups: List[Dict[str, Any]] = []
    for file in base.glob("*.yaml"):
        with open(file, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            if content is None:
                continue
            if isinstance(content, list):
                for entry in content:
                    validated = _validate_group(entry, file)
                    groups.append(validated)
            else:
                validated = _validate_group(content, file)
                groups.append(validated)
    return groups
