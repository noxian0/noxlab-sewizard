"""Backup creation, listing, deletion, and restore helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import shutil


BACKUP_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"


@dataclass(frozen=True)
class BackupEntry:
    path: Path
    source_name: str
    size: int
    created_at: str


class BackupManager:
    def __init__(self, backup_folder: str | Path) -> None:
        self.backup_folder = Path(backup_folder)
        self.backup_folder.mkdir(parents=True, exist_ok=True)

    def set_folder(self, backup_folder: str | Path) -> None:
        self.backup_folder = Path(backup_folder)
        self.backup_folder.mkdir(parents=True, exist_ok=True)

    def create_backup(self, source_file: str | Path) -> Path:
        source = Path(source_file)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Cannot back up missing file: {source}")
        self.backup_folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime(BACKUP_TIME_FORMAT)
        safe_name = sanitize_name(source.name)
        destination = self.backup_folder / f"{safe_name}_{timestamp}.bak"
        counter = 1
        while destination.exists():
            destination = self.backup_folder / f"{safe_name}_{timestamp}_{counter}.bak"
            counter += 1
        shutil.copy2(source, destination)
        return destination

    def list_backups(self, source_file: str | Path | None = None) -> list[BackupEntry]:
        self.backup_folder.mkdir(parents=True, exist_ok=True)
        prefix = None
        if source_file is not None:
            prefix = sanitize_name(Path(source_file).name) + "_"

        entries: list[BackupEntry] = []
        for file_path in self.backup_folder.glob("*.bak"):
            if prefix and not file_path.name.startswith(prefix):
                continue
            stat = file_path.stat()
            entries.append(
                BackupEntry(
                    path=file_path,
                    source_name=_source_name_from_backup(file_path.name),
                    size=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
        entries.sort(key=lambda entry: entry.path.stat().st_mtime, reverse=True)
        return entries

    def restore_backup(self, backup_file: str | Path, target_file: str | Path, backup_current: bool = True) -> Path | None:
        backup = Path(backup_file)
        target = Path(target_file)
        if not backup.exists() or not backup.is_file():
            raise FileNotFoundError(f"Backup not found: {backup}")
        current_backup: Path | None = None
        if backup_current and target.exists():
            current_backup = self.create_backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
        return current_backup

    def delete_backup(self, backup_file: str | Path) -> None:
        backup = Path(backup_file)
        if backup.exists() and backup.is_file() and backup.parent.resolve() == self.backup_folder.resolve():
            backup.unlink()

    def open_folder(self) -> None:
        self.backup_folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.backup_folder))  # type: ignore[attr-defined]
        else:
            raise RuntimeError(f"Open folder manually: {self.backup_folder}")


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return cleaned or "save"


def _source_name_from_backup(backup_name: str) -> str:
    match = re.match(r"(.+)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:_\d+)?\.bak$", backup_name)
    if not match:
        return backup_name
    return match.group(1)
