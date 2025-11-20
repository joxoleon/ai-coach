import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

AVATAR_PATHS = [
    Path(__file__).resolve().parents[2] / "configs" / "avatars.yaml",
    Path(__file__).resolve().parents[2] / "configs" / "avatars.yml",
]


def _get_avatar_file() -> Optional[Path]:
    for path in AVATAR_PATHS:
        if path.exists():
            return path
    return None


def load_avatars() -> List[Dict[str, Any]]:
    path = _get_avatar_file()
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    if not isinstance(data, list):
        return []
    return data


def pick_avatar_for_day(seed: int) -> Optional[Dict[str, Any]]:
    avatars = load_avatars()
    if not avatars:
        return None
    rng = random.Random(seed)
    return rng.choice(avatars)


def pick_random_avatar() -> Optional[Dict[str, Any]]:
    avatars = load_avatars()
    if not avatars:
        return None
    return random.choice(avatars)


def pick_avatar_for_group(group: str) -> Optional[Dict[str, Any]]:
    avatars = load_avatars()
    if not avatars:
        return None
    group_lower = group.lower()
    filtered = [
        avatar
        for avatar in avatars
        if any(group_lower in str(cat).lower() for cat in avatar.get("categories", []))
    ]
    return filtered[0] if filtered else avatars[0]


def pick_quote_for_avatar(avatar: Dict[str, Any]) -> Optional[str]:
    quotes = avatar.get("quotes") if isinstance(avatar, dict) else None
    if not quotes:
        return None
    return random.choice(quotes)
