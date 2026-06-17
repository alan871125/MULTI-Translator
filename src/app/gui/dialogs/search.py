import json
import logging
import PyQt5.QtWidgets as qt
from typing import overload, Literal
from pathlib import Path
from dataclasses import dataclass, asdict, field

import pandas as pd
from deep_translator import GoogleTranslator

from PyQt5 import QtCore
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QDropEvent, QCursor, QIcon
from PyQt5.QtWidgets import QAction, QLineEdit, QTableWidget, QDialogButtonBox

from app.language import LanguagePack
from core.translation import TranslationLevel
from ...models.filters import ColumnFilter, TableFilters

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
L = LanguagePack()

class SearchLineEdit(qt.QLineEdit):
    padding=1
    def __init__(self, parent=None):
        super().__init__(parent)        
        self.buttons = {}
        self.buttons["case"] = qt.QToolButton(self)
        self.buttons["case"].setText("Aa")
        self.buttons["case"].setToolTip("Match Case")
        self.buttons["case"].setCheckable(True)
        self.buttons["case"].setAutoRaise(True) # Makes it look like a flat button without borders
        self.buttons["regex"] = qt.QToolButton(self)
        self.buttons["regex"].setText("(.*)")
        self.buttons["regex"].setToolTip("Use Regular Expression")
        self.buttons["regex"].setCheckable(True)
        self.buttons["regex"].setAutoRaise(True) # Makes it look like a flat button without borders

        self.setStyleSheet("QToolButton { border: none; padding: 0px background:transparent; }") # Remove extra padding around the button
        self.update_button_position()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_button_position()
        
    def update_button_position(self):
        frame = self.style().pixelMetric(qt.QStyle.PM_DefaultFrameWidth)
        n = len(self.buttons)
        
        for i,btn in enumerate(self.buttons.values()):
            size = btn.sizeHint()
            # place it inside the right edge
            x = self.rect().right() - frame - size.width()*(n - i) - self.padding*(n - i)
            y = (self.rect().height() - size.height()) // 2
            btn.move(x, y)

class SearchDialog(qt.QDialog):
    # Note: suppose the replace uses regex if the search does.
    replace_requested = pyqtSignal(dict, str, str)  # filters, replace_text, column
    def __init__(self, filters:TableFilters, parent=None):
        super().__init__(parent)
        self.filters = filters
        self.setWindowTitle(L["search_and_replace"])
        self.resize(400, 100)
        
        self.center_on_parent()
        # 1. Main vertical layout
        layout = qt.QVBoxLayout(self)
        self.filter_entries = {}
        
        # 2. Main Grid Layout to handle perfect alignment
        grid_layout = qt.QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(6)
        
        # 3. Create the Fold Toggle Button
        self.fold_button = qt.QToolButton(self)
        self.fold_button.setText(" 〉") 
        self.fold_button.setCheckable(True)
        self.fold_button.setCursor(Qt.PointingHandCursor)
        self.fold_button.setToolTip("Show/Hide Replace Options")
        
        # Let it expand vertically to match row heights seamlessly
        self.fold_button.setSizePolicy(qt.QSizePolicy.Policy.Fixed, qt.QSizePolicy.Policy.Expanding)
        self.fold_button.setMinimumWidth(28)
        self.fold_button.setMaximumWidth(28)
        #TODO: move to theme
        self.fold_button.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                padding: 2px 4px;
            }
            QToolButton:hover { background: #e0e0e0; }
        """)
        # Place button in Grid: row 0, col 0, spanning 2 rows initially (original & translation)
        grid_layout.addWidget(self.fold_button, 0, 0, 2, 1)
        
        # 4. Loop to populate the two search rows
        search_columns = ["original", "translation"]
        for idx, col in enumerate(search_columns):
            # Form Label
            lbl = qt.QLabel(L[col], self)
            grid_layout.addWidget(lbl, idx,  1) # row idx, col 1
            
            # Form Entry Container
            search_box = qt.QWidget(self)
            search_box.setObjectName("SearchBox")
            box_layout = qt.QHBoxLayout(search_box)
            box_layout.setContentsMargins(5, 2, 5, 2)
            box_layout.setSpacing(4)
            
            if (filter_data := self.filters.get(col)) is not None:
                initial_text = filter_data.text
            else:
                initial_text = ""
            
            entry = SearchLineEdit(self)
            entry.setFrame(False)
            entry.setText(initial_text)
            box_layout.addWidget(entry)
            #TODO: move to theme?
            search_box.setStyleSheet("""
                QWidget#SearchBox {
                    background: white;
                    border: 1px solid #c3c3c3;
                    border-radius: 4px;
                }
                QToolButton:hover { background: #e0e0e0; }
                QToolButton:checked { background: #d0d0d0; border: 1px solid #204080; }
                QToolButton {
                    background: transparent;
                    border: none;
                    border-radius: 3px;
                    font-weight: bold;
                    padding: 2px 4px;
                    color: #204080;
                }
            """)
            
            search_box.setMinimumWidth(300)
            grid_layout.addWidget(search_box, idx, 2) # row idx, col 2
            
            self.filter_entries[col] = {
                "entry": entry,
                "case_btn": entry.buttons["case"],
                "regex_btn": entry.buttons["regex"],
            }
            
        # 5. Containerized Replace Row
        self.replace_widget = qt.QWidget(self)
        replace_container_layout = qt.QHBoxLayout(self.replace_widget)
        replace_container_layout.setContentsMargins(0, 0, 0, 0)
        replace_container_layout.setSpacing(6)
        
        replace_box = qt.QWidget(self)
        replace_box.setStyleSheet("QWidget { background: white; border: 1px solid #c3c3c3; border-radius: 4px; }")
        rb_layout = qt.QHBoxLayout(replace_box)
        rb_layout.setContentsMargins(5, 2, 5, 2)
        
        replace_entry = qt.QLineEdit(self)
        replace_entry.setFrame(False)
        replace_entry.setPlaceholderText("Replace text here...")
        rb_layout.addWidget(replace_entry)
        
        replace_container_layout.addWidget(replace_box, stretch=1)
        
        replace_button = qt.QPushButton(L["replace_all"], self)
        replace_button.setCursor(Qt.PointingHandCursor)
        replace_button.clicked.connect(self.on_replace)
        replace_container_layout.addWidget(replace_button)
        
        # Place the replace widget on row 2, stretching across columns 1 and 2
        grid_layout.addWidget(self.replace_widget, 2, 1, 1, 2)
        self.replace_widget.setVisible(False) 
        
        layout.addLayout(grid_layout)
        
        # 6. Bottom Button Box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        button_box.button(QDialogButtonBox.Reset).clicked.connect(self.reset_filters)
        layout.addWidget(button_box)
        
        # Connect Fold button actions
        self.fold_button.toggled.connect(lambda checked, gl=grid_layout: self.toggle_replace_row(checked, gl))
        self.replace_entry = replace_entry
        
    def center_on_parent(self):
        """Calculates geometry coordinates to place this dialog in the middle of its parent window."""
        if self.parentWidget():
            # Get the geometry of the main window frame
            parent_geo = self.parentWidget().geometry()
            # Get our own dialog frame geometry parameters
            dialog_geo = self.geometry()
            
            # Calculate the absolute center point mapping
            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2
            
            # Snap dialog into position
            self.move(x, y)
    
    def toggle_replace_row(self, checked, grid_layout):
        """Updates layout span and visibility dynamically on fold."""
        # 1. Update visibility
        self.replace_widget.setVisible(checked)
        self.fold_button.setText("﹀" if checked else " 〉")
        
        # 2. Update grid constraints so the button spans dynamically
        # Remove the button from its old layout slot
        grid_layout.removeWidget(self.fold_button)
        
        if checked:
            # If toggled open, stretch the button across 3 rows (0, 1, and 2)
            grid_layout.addWidget(self.fold_button, 0, 0, 3, 1)
        else:
            # If toggled closed, only stretch across the 2 search rows (0 and 1)
            grid_layout.addWidget(self.fold_button, 0, 0, 2, 1)
            
        # 3. Force instant geometry calculation recalculation 
        self.layout().activate()
        qt.QApplication.processEvents()
        self.adjustSize()

    def create_replace_options(self):
        # 2. REPLACE LINE (Bottom Line - Foldable)
        replace_box = qt.QWidget(self)
        replace_box.setObjectName("ReplaceBox")
        rb_layout = qt.QHBoxLayout(replace_box)
        rb_layout.setContentsMargins(5, 2, 5, 2)
        rb_layout.setSpacing(2)
        
        # Indent placeholder spacing underneath the upper arrow
        indent_spacer = qt.QLabel("   ", self)
        rb_layout.addWidget(indent_spacer)
        
        # Replace Label or Icon
        replace_icon = qt.QLabel("✍️", self) # Or leave empty string if you want it blank
        rb_layout.addWidget(replace_icon)
        
        # Replace Input Entry
        replace_entry = qt.QLineEdit(self)
        replace_entry.setFrame(False)
        replace_entry.setPlaceholderText("Replace with...")
        rb_layout.addWidget(replace_entry)
        
        # Set Replace row to hidden initially
        replace_box.setVisible(False)
        return replace_box, replace_entry
            
    def reset_filters(self):
        for controls in self.filter_entries.values():
            controls["entry"].clear()
            controls["regex_btn"].setChecked(False)
            controls["regex_btn"].setText("🔎") # Force reset the icon text too

    def set_filters(self):
        filters = []
        for col, controls in self.filter_entries.items():
            if not (text := controls["entry"].text().strip()):
                continue
            filters.append(ColumnFilter(
                col, text, 
                controls["regex_btn"].isChecked(), 
                controls["case_btn"].isChecked()
            ))
        self.filters.set_filters(filters) # emits signal only once
        
    def get_filters(self) -> list[ColumnFilter]:
        filters = []
        for col, controls in self.filter_entries.items():
            text = controls["entry"].text().strip()
            is_regex = controls["regex_btn"].isChecked()
            match_case = controls["case_btn"].isChecked()
            if text:
                filters.append(ColumnFilter(col, text, is_regex, match_case))
        return filters
    
    def on_replace(self):
        column="original"  #TODO: add option to select which column to replace from
        filters = self.get_filters()
        replace_text = self.replace_entry.text().strip()
        # Emit the replace signal with search criteria and replacement text
        self.replace_requested.emit(filters, replace_text, column)