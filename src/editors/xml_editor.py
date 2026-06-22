"""XML tree preview with validated text editing."""

from __future__ import annotations

import xml.dom.minidom
import xml.etree.ElementTree as ET

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class XmlEditor(QWidget):
    kind = "xml"

    def __init__(self) -> None:
        super().__init__()
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Element", "Attributes", "Text"])
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.textChanged.connect(self._refresh_tree_if_valid)
        self.original_text = ""
        self.loading = False

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def load_text(self, text: str) -> None:
        self.original_text = text
        self.loading = True
        self.editor.setPlainText(pretty_xml(text))
        self.loading = False
        self._populate_tree(self.editor.toPlainText())

    def serialize(self) -> str:
        return self.editor.toPlainText()

    def validate(self) -> tuple[bool, str]:
        try:
            ET.fromstring(self.serialize())
        except ET.ParseError as exc:
            return False, str(exc)
        return True, ""

    def is_modified(self) -> bool:
        return self.serialize().strip() != pretty_xml(self.original_text).strip()

    def changed_summary(self, limit: int = 30) -> list[str]:
        old_lines = pretty_xml(self.original_text).splitlines()
        new_lines = self.serialize().splitlines()
        changes: list[str] = []
        for index in range(max(len(old_lines), len(new_lines))):
            old = old_lines[index] if index < len(old_lines) else ""
            new = new_lines[index] if index < len(new_lines) else ""
            if old != new:
                changes.append(f"line {index + 1}: {old!r} -> {new!r}")
            if len(changes) >= limit:
                changes.append("...")
                break
        return changes

    def search(self, term: str) -> int:
        selections = []
        count = 0
        if term:
            document = self.editor.document()
            cursor = QTextCursor(document)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#7a1e1e"))
            while True:
                cursor = document.find(term, cursor)
                if cursor.isNull():
                    break
                selection = QPlainTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = fmt
                selections.append(selection)
                count += 1
        self.editor.setExtraSelections(selections)
        return count

    def _refresh_tree_if_valid(self) -> None:
        if self.loading:
            return
        valid, _ = self.validate()
        if valid:
            self._populate_tree(self.serialize())

    def _populate_tree(self, text: str) -> None:
        self.tree.clear()
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return
        root_item = make_xml_item(root)
        self.tree.addTopLevelItem(root_item)
        walk_xml(root, root_item)
        root_item.setExpanded(True)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)


def walk_xml(element: ET.Element, item: QTreeWidgetItem) -> None:
    for child in list(element):
        child_item = make_xml_item(child)
        item.addChild(child_item)
        walk_xml(child, child_item)


def make_xml_item(element: ET.Element) -> QTreeWidgetItem:
    attrs = " ".join(f'{key}="{value}"' for key, value in element.attrib.items())
    text = (element.text or "").strip()
    return QTreeWidgetItem([element.tag, attrs, text])


def pretty_xml(text: str) -> str:
    try:
        parsed = xml.dom.minidom.parseString(text.encode("utf-8"))
        return parsed.toprettyxml(indent="  ")
    except Exception:
        return text
