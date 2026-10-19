import logging
from typing import Literal, override, get_args

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QVBoxLayout, QGridLayout, QWidget,
    QLabel, QCheckBox, QPushButton, QLineEdit, QStyle, QSizePolicy, 
    QDialog, QDialogButtonBox, QToolButton, 
)

from qt_extensions.core import TypedSignal
from app.locales import LanguagePack
from app.typing import SearchableColumn
from ...models.filters import ColumnFilter, TableFilters
logger = logging.getLogger(__name__)
L = LanguagePack()

# For Propper type hinting of the signal
SEARCH_COLUMNS = ("file", "key", "original", "translation")
assert all(col in get_args(SearchableColumn) for col in SEARCH_COLUMNS), "SEARCH_COLUMNS must match SearchableColumn type"
class SearchLineEdit(QLineEdit):
    padding=1
    def __init__(self, parent=None):
        super().__init__(parent)        
        self.buttons = {}
        self.buttons["case"] = QToolButton(self)
        self.buttons["case"].setText("Aa")
        self.buttons["case"].setToolTip("Match Case")
        self.buttons["case"].setCheckable(True)
        self.buttons["case"].setAutoRaise(True) # Makes it look like a flat button without borders
        self.buttons["regex"] = QToolButton(self)
        self.buttons["regex"].setText("(.*)")
        self.buttons["regex"].setToolTip("Use Regular Expression")
        self.buttons["regex"].setCheckable(True)
        self.buttons["regex"].setAutoRaise(True) # Makes it look like a flat button without borders

        self.setStyleSheet("QToolButton { border: none; padding: 0px background:transparent; }") # Remove extra padding around the button
        self.update_button_position()
    
    @override
    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        self.update_button_position()
        
    def update_button_position(self):
        if (style := self.style()) is not None:
            frame = style.pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth)
        else:
            logger.error("Style is not available, using fallback frame width of 2 pixels.")
            frame = 2  # Fallback value if style is not available
        n = len(self.buttons)
        
        for i,btn in enumerate(self.buttons.values()):
            size = btn.sizeHint()
            # place it inside the right edge
            x = self.rect().right() - frame - size.width()*(n - i) - self.padding*(n - i)
            y = (self.rect().height() - size.height()) // 2
            btn.move(x, y)

class SearchDialog(QDialog):
    # Note: suppose the replace uses regex if the search does.
    replace_requested: TypedSignal[dict[SearchableColumn, ColumnFilter], str, Literal["original", "translation"]] = TypedSignal(dict, str, Literal["original", "translation"])  # filters, replace_text, column
    SEARCH_COLUMNS =  SEARCH_COLUMNS
    
    REPLACE_START_ROW = 2  # The row index in the grid layout where the replace row starts  
    def __init__(self, filters:TableFilters, parent=None):
        super().__init__(parent)
        self.filters = filters
        self.setWindowTitle(L["search_and_replace"])
        self.resize(400, 100)
        
        self.center_on_parent()
        # 1. Main vertical layout
        layout = QVBoxLayout(self)
        self.filter_entries = {}
        
        # 2. Main Grid Layout to handle perfect alignment
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(6)
        
        # 3. Create the Fold Toggle Button
        self.fold_button = QToolButton(self)
        self.fold_button.setText(" 〉") 
        self.fold_button.setCheckable(True)
        self.fold_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fold_button.setToolTip("Show/Hide Replace Options")
        
        # Let it expand vertically to match row heights seamlessly
        self.fold_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.fold_button.setMinimumWidth(28)
        self.fold_button.setMaximumWidth(28)
        #TODO: move to theme
        self.fold_button.setObjectName("FoldButton")
        # Place button in Grid: row 0, col 0, spanning 2 rows initially (original & translation)
        grid_layout.addWidget(self.fold_button, self.REPLACE_START_ROW, 0, 2, 1)
        
        # 4. Loop to populate the two search rows
        
        for idx, col in enumerate(self.SEARCH_COLUMNS):
            # Form Label
            lbl = QLabel(L[col], self)
            grid_layout.addWidget(lbl, idx,  1) # row idx, col 1
            
            # Form Entry Container
            search_box = QWidget(self)
            search_box.setObjectName("SearchBox")
            box_layout = QHBoxLayout(search_box)
            box_layout.setContentsMargins(5, 2, 5, 2)
            box_layout.setSpacing(4)
            
            if (filter_data := self.filters.get(col)) is not None:
                initial_text = filter_data.text
            else:
                initial_text = ""
            
            entry = SearchLineEdit(self)
            entry.setFrame(False)
            entry.setText(initial_text)
            entry.buttons["case"].setChecked(filter_data.match_case if filter_data else False)
            entry.buttons["regex"].setChecked(filter_data.is_regex if filter_data else False)
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
        self.replace_widget = QWidget(self)
        replace_container_layout = QHBoxLayout(self.replace_widget)
        replace_container_layout.setContentsMargins(0, 0, 0, 0)
        replace_container_layout.setSpacing(6)
        
        replace_box = QWidget(self)
        # replace_box.setStyleSheet("QWidget { background: white; border: 1px solid #c3c3c3; border-radius: 4px; }")
        rb_layout = QHBoxLayout(replace_box)
        rb_layout.setContentsMargins(5, 2, 5, 2)
        
        replace_entry = QLineEdit(self)
        replace_entry.setFrame(False)
        replace_entry.setPlaceholderText("Replace text here...")
        rb_layout.addWidget(replace_entry)
        
        replace_container_layout.addWidget(replace_box, stretch=1)
        
        self.replace_source_checkbox = QCheckBox(L["replace_from_original"], self)
        self.replace_source_checkbox.setChecked(False)
        self.replace_source_checkbox.setToolTip(L['replace_from_original.tooltip'])
        replace_container_layout.addWidget(self.replace_source_checkbox)

        replace_button = QPushButton(L["replace_all"], self)
        replace_button.setCursor(Qt.CursorShape.PointingHandCursor)
        replace_button.clicked.connect(self.on_replace)
        replace_container_layout.addWidget(replace_button)
        
        # Place the replace widget after the last search row, spanning 2 columns (label + entry)
        grid_layout.addWidget(self.replace_widget, len(self.SEARCH_COLUMNS), 1, 1, 2)
        self.replace_widget.setVisible(False) 
        
        layout.addLayout(grid_layout)
        
        # 6. Bottom Button Box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Reset, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        assert (reset_button:= button_box.button(QDialogButtonBox.StandardButton.Reset)) is not None
        reset_button.clicked.connect(self.reset_filters)
        layout.addWidget(button_box)
        
        # Connect Fold button actions
        self.fold_button.toggled.connect(lambda checked, gl=grid_layout: self.toggle_replace_row(checked, gl))
        self.replace_entry = replace_entry
    
    @override
    def accept(self) -> None:
        self.set_filters()
        super().accept()  # Calls standard QDialog.accept() and closes dialog
    
    def center_on_parent(self):
        """Calculates geometry coordinates to place this dialog in the middle of its parent window."""
        if parent := self.parentWidget():
            # Get the geometry of the main window frame
            parent_geo = parent.geometry()
            # Get our own dialog frame geometry parameters
            dialog_geo = self.geometry()
            
            # Calculate the absolute center point mapping
            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2
            
            # Snap dialog into position
            self.move(x, y)
    
    def toggle_replace_row(self, checked, grid_layout:QGridLayout):
        """Updates layout span and visibility dynamically on fold."""
        # 1. Update visibility
        self.replace_widget.setVisible(checked)
        self.fold_button.setText("﹀" if checked else " 〉")
        
        # 2. Update grid constraints so the button spans dynamically
        # Remove the button from its old layout slot
        grid_layout.removeWidget(self.fold_button)
        
        if checked:
            # If toggled open, stretch the button across 3 rows last three rows
            grid_layout.addWidget(self.fold_button, self.REPLACE_START_ROW, 0, 3, 1)
        else:
            # If toggled closed, only stretch across the 2 search rows (original & translation)
            grid_layout.addWidget(self.fold_button, self.REPLACE_START_ROW, 0, 2, 1)
            
        # 3. Force instant geometry calculation recalculation 
        assert (layout:=self.layout()) is not None
        layout.activate()
        QApplication.processEvents()
        self.adjustSize()
    
    def reset_filters(self):
        for controls in self.filter_entries.values():
            controls["entry"].clear()
            controls["regex_btn"].setChecked(False)
            controls["regex_btn"].setText("🔎") # Force reset the icon text too

    def set_filters(self):
        self.filters.set_filters(self.get_filters().values()) # emits signal only once
        
    def get_filters(self) -> dict[SearchableColumn, ColumnFilter]:
        filters = {}
        for col, controls in self.filter_entries.items():
            if not (text := controls["entry"].text().strip()):
                continue
            filters[col] = ColumnFilter(
                col, text, 
                controls["regex_btn"].isChecked(), 
                controls["case_btn"].isChecked()
            )
        return filters
    
    def on_replace(self):
        if self.replace_source_checkbox.isChecked():
            column = "original"
        else:
            column = "translation"
        filters = self.get_filters() # gets filters without setting
        replace_text = self.replace_entry.text().strip()
        # Emit the replace signal with search criteria and replacement text
        self.replace_requested.emit(filters, replace_text, column)