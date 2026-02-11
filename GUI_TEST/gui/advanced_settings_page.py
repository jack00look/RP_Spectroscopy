from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QGroupBox, QScrollArea, QPushButton,
                                QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, Signal, Slot
from copy import deepcopy


class AdvancedSettingsPage(QWidget):
    """
    Displays a scrollable list of QGroupBox widgets, one per ui_label group
    found in the advanced_settings section of the board YAML.
    Each group box contains a QTableWidget with Key/Value columns.

    Emits sig_advanced_setting_changed(dict) with the full updated settings
    whenever the user edits a value.
    """
    sig_back = Signal()
    sig_advanced_setting_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self._settings = {}       # deep copy of the live settings dict
        self._is_populating = False

        # --- Layout ---
        outer = QVBoxLayout(self)

        # Title
        title = QLabel("Advanced Settings")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        outer.addWidget(title)

        # Scroll area for group boxes
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._scroll_content)
        outer.addWidget(self._scroll, 1)

        # Back button
        btn_back = QPushButton("Back")
        btn_back.setFixedWidth(120)
        btn_back.clicked.connect(self.sig_back.emit)
        btn_container = QHBoxLayout()
        btn_container.addStretch()
        btn_container.addWidget(btn_back)
        btn_container.addStretch()
        outer.addLayout(btn_container)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @Slot(dict)
    def load_advanced_settings(self, settings: dict):
        """Populate the page from the advanced_settings dict."""
        self._is_populating = True
        self._settings = deepcopy(settings)

        # Clear previous group boxes
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Build a QGroupBox + QTableWidget for every top-level key
        for group_key, group_data in self._settings.items():
            if not isinstance(group_data, dict):
                continue
            ui_label = group_data.get("ui_label", group_key)

            group_box = QGroupBox(ui_label)
            gbox_layout = QVBoxLayout(group_box)

            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Setting", "Value"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)

            # Flatten nested dicts into rows
            rows = []
            self._flatten(group_data, prefix="", rows=rows)

            table.setRowCount(len(rows))
            for i, (dot_path, val) in enumerate(rows):
                # Setting name (read-only)
                key_item = QTableWidgetItem(dot_path)
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                table.setItem(i, 0, key_item)

                # Value (editable)
                val_item = QTableWidgetItem(str(val))
                val_item.setData(Qt.UserRole, (group_key, dot_path))
                table.setItem(i, 1, val_item)

            # Auto-size rows
            table.resizeRowsToContents()

            # Connect edits
            table.cellChanged.connect(self._on_cell_changed)

            gbox_layout.addWidget(table)
            self._scroll_layout.addWidget(group_box)

        self._is_populating = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _flatten(self, data: dict, prefix: str, rows: list):
        """
        Recursively walk a nested dict and produce (dot_path, leaf_value) tuples.
        Skips the 'ui_label' key. Dicts with a 'value' key are treated as leaf
        parameters; `options` is stored alongside for display but the editable
        cell is just the value.
        """
        for key, val in data.items():
            if key == "ui_label":
                continue

            path = f"{prefix}.{key}" if prefix else key

            if isinstance(val, dict):
                if "value" in val:
                    # Leaf parameter — show value, options are informational
                    rows.append((path, val["value"]))
                else:
                    # Nested group — recurse
                    self._flatten(val, path, rows)
            else:
                rows.append((path, val))

    def _on_cell_changed(self, row, column):
        """Handle edits in any group table."""
        if self._is_populating:
            return
        if column != 1:
            return

        # Determine which table emitted this
        table = self.sender()
        item = table.item(row, column)
        if not item:
            return

        meta = item.data(Qt.UserRole)
        if not meta:
            return
        group_key, dot_path = meta
        new_text = item.text()

        # Parse value back into correct type
        new_val = self._parse_value(new_text)

        # Update internal settings dict
        self._set_nested(self._settings[group_key], dot_path, new_val)

        self.sig_advanced_setting_changed.emit(deepcopy(self._settings))

    @staticmethod
    def _parse_value(text: str):
        """Convert a string back to bool / int / float / list / str."""
        stripped = text.strip()

        # Bool
        if stripped.lower() in ("true", "false"):
            return stripped.lower() == "true"

        # List (comma-separated or [...])
        if stripped.startswith("[") and stripped.endswith("]"):
            stripped = stripped[1:-1]
        if "," in stripped:
            parts = [p.strip() for p in stripped.split(",")]
            parsed = []
            for p in parts:
                try:
                    parsed.append(float(p) if "." in p else int(p))
                except ValueError:
                    parsed.append(p)
            return parsed

        # Int / Float
        try:
            if "." in stripped:
                return float(stripped)
            return int(stripped)
        except ValueError:
            return stripped  # keep as string

    @staticmethod
    def _set_nested(d: dict, dot_path: str, value):
        """Set a value in a nested dict using a dot-separated path."""
        keys = dot_path.split(".")
        for k in keys[:-1]:
            d = d[k]
        # If the leaf is a dict with a 'value' key, set that
        if isinstance(d.get(keys[-1]), dict) and "value" in d[keys[-1]]:
            d[keys[-1]]["value"] = value
        else:
            d[keys[-1]] = value
