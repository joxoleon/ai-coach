import yaml
from pathlib import Path
from typing import Any, Dict, List

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
EXCLUDED_STEMS = {"avatars"}


class LoadedConfigs(list):
    """Holds configs by module while remaining list-compatible for the selector."""

    def __init__(self, modules: Dict[str, List[Dict[str, Any]]], flat: List[Dict[str, Any]]):
        super().__init__(flat)
        self.modules = modules
        self.flat = flat


def _validate_group(data: Dict[str, Any], path: Path) -> Dict[str, Any]:
    if "group" not in data or "items" not in data:
        raise ValueError(f"Config {path.name} missing required keys")
    if not isinstance(data["items"], list):
        raise ValueError(f"Config {path.name} items must be a list")
    for item in data["items"]:
        if "name" not in item or "importance" not in item:
            raise ValueError(f"Item in {path.name} missing name or importance")
    return data


def load_configs(config_dir: Path | None = None) -> LoadedConfigs:
    base = config_dir or CONFIG_DIR
    configs: Dict[str, List[Dict[str, Any]]] = {}
    flat_groups: List[Dict[str, Any]] = []
    seen: set[str] = set()
    patterns = ("*.yaml", "*.yml")
    for pattern in patterns:
        for file in sorted(base.glob(pattern)):
            if file.stem in EXCLUDED_STEMS or file.stem in seen:
                continue
            seen.add(file.stem)
            with open(file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if content is None:
                    continue
                entries: List[Dict[str, Any]] = []
                if isinstance(content, list):
                    for entry in content:
                        entries.append(_validate_group(entry, file))
                elif isinstance(content, dict):
                    entries.append(_validate_group(content, file))
                if entries:
                    configs[file.stem] = entries
                    flat_groups.extend(entries)

    return LoadedConfigs(configs, flat_groups)
