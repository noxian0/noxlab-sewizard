"""Local settings and recent-file storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path


APP_FOLDER_NAME = "NOXLAB SEWIZARD"


def app_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / ".local" / "share"
    path = base / APP_FOLDER_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_backup_folder() -> Path:
    return Path.cwd() / "backups"


@dataclass
class AppSettings:
    backup_folder: str
    always_backup: bool = True
    unknown_read_only: bool = True
    advanced_hex_editing: bool = False
    theme: str = "dark-red"
    max_recent: int = 12

    @classmethod
    def defaults(cls) -> "AppSettings":
        return cls(backup_folder=str(default_backup_folder()))


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (app_data_dir() / "settings.json")

    def load(self) -> AppSettings:
        defaults = AppSettings.defaults()
        if not self.path.exists():
            return defaults

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return defaults

        merged = asdict(defaults)
        merged.update({key: value for key, value in raw.items() if key in merged})
        return AppSettings(**merged)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


class RecentStore:
    def __init__(self, path: Path | None = None, max_items: int = 12) -> None:
        self.path = path or (app_data_dir() / "recent.json")
        self.max_items = max_items

    def load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data if isinstance(item, str)]

    def add(self, file_path: Path) -> None:
        resolved = str(file_path)
        items = [item for item in self.load() if item != resolved]
        items.insert(0, resolved)
        self.save(items[: self.max_items])

    def clear(self) -> None:
        self.save([])

    def save(self, items: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")
