"""JSON tree editor."""

from __future__ import annotations

import copy
import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


PATH_ROLE = Qt.ItemDataRole.UserRole
TYPE_ROLE = Qt.ItemDataRole.UserRole + 1


class JsonEditor(QWidget):
    kind = "json"

    def __init__(self) -> None:
        super().__init__()
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Key", "Type", "Value"])
        self.tree.itemChanged.connect(self._item_changed)
        self.data: Any = None
        self.original_data: Any = None
        self.loading = False

        self.add_button = QPushButton("Add Field")
        self.remove_button = QPushButton("Remove")
        self.add_button.clicked.connect(self.add_field)
        self.remove_button.clicked.connect(self.remove_selected)

        actions = QHBoxLayout()
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(actions)
        layout.addWidget(self.tree)

    def load_text(self, text: str) -> None:
        self.loading = True
        self.tree.clear()
        self.data = json.loads(text)
        self.original_data = copy.deepcopy(self.data)
        root = self._make_item("root", self.data, [])
        self.tree.addTopLevelItem(root)
        root.setExpanded(True)
        self._populate(root, self.data, [])
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.loading = False

    def serialize(self) -> str:
        return json.dumps(self.data, indent=2, ensure_ascii=False)

    def validate(self) -> tuple[bool, str]:
        try:
            json.loads(self.serialize())
        except json.JSONDecodeError as exc:
            return False, str(exc)
        return True, ""

    def is_modified(self) -> bool:
        return self.data != self.original_data

    def changed_summary(self, limit: int = 50) -> list[str]:
        old = flatten_json(self.original_data)
        new = flatten_json(self.data)
        keys = sorted(set(old) | set(new))
        changes: list[str] = []
        for key in keys:
            if old.get(key) != new.get(key):
                changes.append(f"{key}: {old.get(key)!r} -> {new.get(key)!r}")
            if len(changes) >= limit:
                changes.append("...")
                break
        return changes

    def search(self, term: str) -> int:
        count = 0
        self._clear_item_brushes()
        if not term:
            return 0
        needle = term.casefold()
        for item in self._all_items():
            haystack = " ".join(item.text(col) for col in range(3)).casefold()
            if needle in haystack:
                brush = QBrush(QColor("#7a1e1e"))
                for col in range(3):
                    item.setBackground(col, brush)
                count += 1
                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
        return count

    def add_field(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            item = self.tree.topLevelItem(0)
        path = item.data(0, PATH_ROLE) or []
        target = get_at_path(self.data, path)
        if not isinstance(target, dict):
            QMessageBox.information(self, "Add Field", "Select a JSON object to add a field.")
            return
        key, ok = QInputDialog.getText(self, "Add Field", "Key:")
        if not ok or not key:
            return
        if key in target:
            QMessageBox.warning(self, "Add Field", "That key already exists.")
            return
        value, ok = QInputDialog.getText(self, "Add Field", "Value:")
        if not ok:
            return
        target[key] = parse_json_scalar(value, "")
        self._reload_preserving_expansion()

    def remove_selected(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        path = item.data(0, PATH_ROLE) or []
        if not path:
            QMessageBox.information(self, "Remove", "The root object cannot be removed.")
            return
        parent, key = get_parent_at_path(self.data, path)
        if isinstance(parent, dict):
            parent.pop(key, None)
        elif isinstance(parent, list) and isinstance(key, int):
            parent.pop(key)
        self._reload_preserving_expansion()

    def _populate(self, item: QTreeWidgetItem, value: Any, path: list[Any]) -> None:
        if isinstance(value, dict):
            for key, child_value in value.items():
                child_path = path + [key]
                child = self._make_item(str(key), child_value, child_path)
                item.addChild(child)
                self._populate(child, child_value, child_path)
        elif isinstance(value, list):
            for index, child_value in enumerate(value):
                child_path = path + [index]
                child = self._make_item(f"[{index}]", child_value, child_path)
                item.addChild(child)
                self._populate(child, child_value, child_path)

    def _make_item(self, key: str, value: Any, path: list[Any]) -> QTreeWidgetItem:
        type_name = type_label(value)
        value_text = "" if isinstance(value, (dict, list)) else json_scalar_to_text(value)
        item = QTreeWidgetItem([key, type_name, value_text])
        item.setData(0, PATH_ROLE, path)
        item.setData(0, TYPE_ROLE, type_name)
        flags = item.flags()
        if not isinstance(value, (dict, list)):
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        return item

    def _item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self.loading:
            return
        if column != 2:
            self._reset_item_labels(item)
            return
        path = item.data(0, PATH_ROLE)
        if path is None:
            return
        parent, key = get_parent_at_path(self.data, path)
        old_value = parent[key] if isinstance(parent, dict) else parent[int(key)]
        try:
            new_value = parse_json_scalar(item.text(2), old_value)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid JSON Value", str(exc))
            self.loading = True
            item.setText(2, json_scalar_to_text(old_value))
            self.loading = False
            return
        if isinstance(parent, dict):
            parent[key] = new_value
        else:
            parent[int(key)] = new_value
        self.loading = True
        item.setText(1, type_label(new_value))
        self.loading = False

    def _reset_item_labels(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, PATH_ROLE) or []
        value = self.data if not path else get_at_path(self.data, path)
        key = "root"
        if path:
            key = f"[{path[-1]}]" if isinstance(path[-1], int) else str(path[-1])
        self.loading = True
        item.setText(0, key)
        item.setText(1, type_label(value))
        self.loading = False

    def _reload_preserving_expansion(self) -> None:
        expanded = {tuple(item.data(0, PATH_ROLE) or []) for item in self._all_items() if item.isExpanded()}
        text = self.serialize()
        self.load_text(text)
        for item in self._all_items():
            if tuple(item.data(0, PATH_ROLE) or []) in expanded:
                item.setExpanded(True)

    def _all_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []

        def walk(item: QTreeWidgetItem) -> None:
            items.append(item)
            for index in range(item.childCount()):
                walk(item.child(index))

        for index in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(index))
        return items

    def _clear_item_brushes(self) -> None:
        blank = QBrush()
        for item in self._all_items():
            for col in range(3):
                item.setBackground(col, blank)


def type_label(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def json_scalar_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def parse_json_scalar(text: str, old_value: Any) -> Any:
    if isinstance(old_value, bool):
        lowered = text.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
        raise ValueError("Expected a boolean value.")
    if old_value is None:
        if text.strip().lower() == "null":
            return None
        return text
    if isinstance(old_value, int) and not isinstance(old_value, bool):
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError("Expected an integer value.") from exc
    if isinstance(old_value, float):
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError("Expected a number value.") from exc
    stripped = text.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    if stripped.lower() == "null":
        return None
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return text


def get_at_path(data: Any, path: list[Any]) -> Any:
    current = data
    for part in path:
        current = current[part]
    return current


def get_parent_at_path(data: Any, path: list[Any]) -> tuple[Any, Any]:
    if not path:
        return None, None
    parent = get_at_path(data, path[:-1])
    return parent, path[-1]


def flatten_json(data: Any, prefix: str = "$") -> dict[str, Any]:
    values: dict[str, Any] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            values.update(flatten_json(value, f"{prefix}.{key}"))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            values.update(flatten_json(value, f"{prefix}[{index}]"))
    else:
        values[prefix] = data
    return values
