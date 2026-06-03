import PyQt5.QtWidgets as qt
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QModelIndex, QTimer, QAbstractTableModel
from PyQt5.QtGui import QDropEvent, QCursor, QIcon
from PyQt5.QtWidgets import QTableWidget, QDialogButtonBox
from dataclasses import dataclass, asdict, field

import json
import pandas as pd
import logging

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class TranslationTableModel(QAbstractTableModel):
    _columns = ["File", "ID", "Attribute", "Original", "Translation"]
    _COLWIDTHS = [100, 20, 100, 200, 200]
    def __init__(self, data):
        super().__init__()
        self._data:pd.DataFrame = pd.DataFrame(data, columns=self._columns)
        self._filtered_data = None
        self.translated_mapping = {}
        self.filters = {}

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
        return section + 1

    def load_actors(self, filename):
        with open(filename, "r", encoding="utf-8") as f:
            actors = json.load(f)
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            _data = []
            for attr in ["name", "nickname", "profile"]:
                if original := actor.get(attr, ""):
                    translation = self.translated_mapping.get(original, "")
                    _data.append({
                        "File": filename,
                        "ID": actor.get("id", ""),
                        "Attribute": attr,
                        "Original": original,
                        "Translation": translation
                    })
            self._data = pd.concat([self._data, pd.DataFrame(_data)], ignore_index=True)
        self.layoutChanged.emit()
    
    def set_filters(self, filters):
        # filters: dict of {column: substring}
        self.filters = filters or {}
        # clear cached filtered data so it will be recalculated
        self._filtered_data = None
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return len(self.filtered_data)
    
    @property
    def filtered_data(self):
        if not self.filters:
            return self._data
        if self._filtered_data is not None:
            return self._filtered_data

        # Build boolean mask for all filters (case-insensitive substring match)
        mask = pd.Series([True] * len(self._data), index=self._data.index)
        for col, text in self.filters.items():
            if col not in self._data.columns:
                continue
            # ensure strings and perform case-insensitive substring match
            mask &= self._data[col].astype(str).str.contains(text, case=False, regex=False, na=False)

        self._filtered_data = self._data[mask].reset_index(drop=True)
        return self._filtered_data
    
    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)
    
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if not index.isValid():
                return None
            r = index.row()
            c = index.column()
            if r < 0 or r >= len(self.filtered_data):
                return None
            if c < 0 or c >= len(self._columns):
                return None
            row = self.filtered_data.iloc[r]
            col = self._columns[c]
            return row.get(col, "")


@dataclass
class TableFilters:
    File: str = ""
    Attribute: str = ""
    Original: str = ""
    Translation: str = ""
    
class FilterDialog(qt.QDialog):
    def __init__(self, parent=None, filters=None):
        super().__init__(parent)
        filters = filters or {}
        self.setWindowTitle("Filter")
        layout = qt.QVBoxLayout(self)
        self.filter_entries = {}
        for col in TranslationTableModel._columns:
            if col == "ID":
                continue
            label = qt.QLabel(col, self)
            layout.addWidget(label)
            entry = qt.QLineEdit(self)
            entry.setText(filters.get(col, ""))
            layout.addWidget(entry)
            self.filter_entries[col] = entry
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Reset).clicked.connect(self.reset_filters)
        layout.addWidget(button_box)
        
    def reset_filters(self):
        for entry in self.filter_entries.values():
            entry.clear()

    def get_filters(self):
        filters = {}
        for col, entry in self.filter_entries.items():
            text = entry.text().strip()
            if text:
                filters[col] = text
        return filters

    
# Actors.json: name, nickname, profile
class TranslationApp(qt.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPG Translator")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)
        self.initUI()
    
    def open_filter_menu(self):
        # Popup a filter Menu with Column: entries for columns in the table.
        dialog = FilterDialog(self, filters=self.model.filters)
        dialog.exec_()
        filters = dialog.get_filters()
        # Apply the filters to the table model
        self.model.set_filters(filters)
        
    def debug(self):
        with open("test/dictionary.json", "r", encoding="utf-8") as f:
            self.model.translated_mapping = json.load(f)
        self.model.load_actors("test/Actors.json")
            
    def initUI(self):
        self.top_bar = self.menuBar()
        self.central_widget = qt.QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = qt.QVBoxLayout(self.central_widget)
        
        button_layout = qt.QHBoxLayout()
        filter_button = qt.QPushButton("Filter", self)
        filter_button.clicked.connect(self.open_filter_menu)
        button_layout.addWidget(filter_button)
        
        self.table = qt.QTableView(self)
        self.model = TranslationTableModel([])
        self.debug()  # Load test data # Remove this line in production #TODO
        self.table.setModel(self.model)
        
        self.main_layout.addLayout(button_layout)
        self.main_layout.addWidget(self.table)
        
        for col, width in enumerate(TranslationTableModel._COLWIDTHS):
            self.table.setColumnWidth(col, width)
    

if __name__ == "__main__":
    app = qt.QApplication([])
    translator = TranslationApp()
    translator.show()
    app.exec_()