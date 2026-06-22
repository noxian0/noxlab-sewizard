"""INI/CFG section and key editor."""

from __future__ import annotations

import configparser
import io

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


SECTION_ROLE = Qt.ItemDataRole.UserRole
KEY_ROLE = Qt.ItemDataRole.UserRole + 1


class IniEditor(QWidget):
    kind = "ini"

    def __init__(self) -> None:
        super().__init__()
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Section", "Key", "Value"])
        self.tree.itemChanged.connect(self._item_changed)
        self.parser = configparser.ConfigParser()
        self.original_text = ""
        self.loading = False

        self.add_key_button = QPushButton("Add Key")
        self.remove_button = QPushButton("Remove")
        self.add_key_button.clicked.connect(self.add_key)
        self.remove_button.clicked.connect(self.remove_selected)

        actions = QHBoxLayout()
        actions.addWidget(self.add_key_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(actions)
        layout.addWidget(self.tree)

    def load_text(self, text: str) -> None:
        parser = configparser.ConfigParser()
        parser.read_string(text)
        self.parser = parser
        self.original_text = text
        self._populate()

    def serialize(self) -> str:
        output = io.StringIO()
        self.parser.write(output)
        return output.getvalue()

    def validate(self) -> tuple[bool, str]:
        try:
            parser = configparser.ConfigParser()
            parser.read_string(self.serialize())
        except configparser.Error as exc:
            return False, str(exc)
        return True, ""

    def is_modified(self) -> bool:
        return self.serialize().strip() != self.original_text.strip()

    def changed_summary(self, limit: int = 50) -> list[str]:
        old = configparser.ConfigParser()
        old.read_string(self.original_text)
        changes: list[str] = []
        sections = sorted(set(old.sections()) | set(self.parser.sections()))
        for section in sections:
            old_keys = set(old[section].keys()) if old.has_section(section) else set()
            new_keys = set(self.parser[section].keys()) if self.parser.has_section(section) else set()
            for key in sorted(old_keys | new_keys):
                old_value = old[section].get(key) if old.has_section(section) and key in old[section] else None
                new_value = self.parser[section].get(key) if self.parser.has_section(section) and key in self.parser[section] else None
                if old_value != new_value:
                    changes.append(f"{section}.{key}: {old_value!r} -> {new_value!r}")
                if len(changes) >= limit:
                    changes.append("...")
                    return changes
        return changes

    def search(self, term: str) -> int:
        count = 0
        blank = QBrush()
        for item in self._all_items():
            for col in range(3):
                item.setBackground(col, blank)
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

    def add_key(self) -> None:
        item = self.tree.currentItem()
        section = item.data(0, SECTION_ROLE) if item else None
        if not section:
            section, ok = QInputDialog.getText(self, "Add Key", "Section:")
            if not ok or not section:
                return
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        key, ok = QInputDialog.getText(self, "Add Key", "Key:")
        if not ok or not key:
            return
        value, ok = QInputDialog.getText(self, "Add Key", "Value:")
        if not ok:
            return
        self.parser.set(section, key, value)
        self._populate()

    def remove_selected(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        section = item.data(0, SECTION_ROLE)
        key = item.data(0, KEY_ROLE)
        if section and key:
            self.parser.remove_option(section, key)
        elif section:
            if QMessageBox.question(self, "Remove Section", f"Remove [{section}]?") == QMessageBox.StandardButton.Yes:
                self.parser.remove_section(section)
        self._populate()

    def _populate(self) -> None:
        self.loading = True
        self.tree.clear()
        for section in self.parser.sections():
            section_item = QTreeWidgetItem([section, "", ""])
            section_item.setData(0, SECTION_ROLE, section)
            self.tree.addTopLevelItem(section_item)
            section_item.setExpanded(True)
            for key, value in self.parser[section].items():
                item = QTreeWidgetItem(["", key, value])
                item.setData(0, SECTION_ROLE, section)
                item.setData(0, KEY_ROLE, key)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                section_item.addChild(item)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.loading = False

    def _item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self.loading:
            return
        section = item.data(0, SECTION_ROLE)
        key = item.data(0, KEY_ROLE)
        if column != 2:
            self.loading = True
            item.setText(0, "")
            item.setText(1, key or "")
            self.loading = False
            return
        if section and key:
            self.parser.set(section, key, item.text(2))

    def _all_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        for index in range(self.tree.topLevelItemCount()):
            section = self.tree.topLevelItem(index)
            items.append(section)
            for child_index in range(section.childCount()):
                items.append(section.child(child_index))
        return items
