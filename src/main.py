import json
import logging
import pandas as pd
import PyQt5.QtWidgets as qt
from typing import cast
from pathlib import Path
from dataclasses import dataclass, asdict, field
from deep_translator import GoogleTranslator

from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QModelIndex, QTimer, QAbstractTableModel
from PyQt5.QtGui import QDropEvent, QCursor, QIcon
from PyQt5.QtWidgets import QTableWidget, QDialogButtonBox

from app.language import LanguagePack
from app.settings import Settings, SettingsDialog
from utils import walk_json

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
L = LanguagePack()
TRANSLATION_FIELDS = {
    "Actors": ["name", "nickname", "profile"],
    "Armors": ["name", "description"],
    "Items":  ["name", "description"],
    "Classes": ["name"],
    "Enemies": ["name"],
    
}
EVENT_TRANSLATION_CODES = {
    102: "ShowChoices",  # Show Choices
    108: "Comment",      # Comment
    401: "Text",         # Text data
    402: "ChoiceBranch", # Choice Branch
    408: "Comment",      # Comment
    # 357: "Plugin",
    # 355, # Script #gameMessage.add("Some text"); #TODO: parse the script for translatable text
}
def translate(source, source_lang="auto", target_lang="en"):
    if not source or not source.strip():
        return
    # Call translation API (e.g. Google Translate) and update translation
    try:
        translated = GoogleTranslator(source_lang, target_lang).translate(source)
    except Exception as e:
        logger.error(f"Translation API error: {e}")
    return translated

class TranslationTableModel(QAbstractTableModel):
    _columns = ["File", "ID", "Attribute", "Original", "Translated"]
    _COLWIDTHS = [100, 20, 80, 500, 500]
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
                return L[self._columns[section]]
        return section + 1

    def load_map_data(self, filename):
        filename = Path(filename)
        with open(filename, "r", encoding="utf-8") as f:
            map_data = json.load(f)
        events = map_data.get("events", [])
        logger.info(f"Loaded map data from {filename}, found {len(events)} events")
        for page in events:
            if page is None:
                continue
            self.load_events(filename=filename, data=page.get("pages", []))
    
    def load_events(self, filename, data=None):
        """        
        Example of event data structure:
        ```
        [
          ...,
          {"id": 2, "list": [{"code": 401, "indent": 0, "parameters": ["Translatable Text"]}]            
        ]            
        ```
        """
        if data is None:
            if filename is None:
                return
            filename = Path(filename)
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        assert data is not None, "Data must be provided either through filename or directly"
        logger.debug(f"Loading events from {filename if filename else 'provided data'}, total items: {len(data)}")
        _data = []
        for item in data:
            if not isinstance(item, dict):
                continue
            for command in item.get("list", []):
                code = command.get("code")
                if cmd_type:=EVENT_TRANSLATION_CODES.get(code):
                    for param, current_path, parent in walk_json(command.get("parameters", [])):
                        if isinstance(param, str) and param.strip():
                            _data.append(
                                a:=self.forge_data(
                                    filename.stem, item, f"CMD:{cmd_type}", param, 
                                    _parent=parent, _key=current_path[-1] if current_path else None,
                                    Path="/".join(current_path)
                                )
                            )
        self._data = pd.concat([self._data, pd.DataFrame(_data)], ignore_index=True)
        self.layoutChanged.emit()
    
                    
    def forge_data(self, filename: str, item, attr, param, _parent=None, _key=None, **kwargs):
        translation = self.translated_mapping.get(param, "")
        return {
            "File": filename,
            "ID": item.get("id", ""),
            "Attribute": attr,
            "Original": param,
            "Translated": translation,
            ".parent":_parent, # the parent object that contains this text
            ".key": _key, # the key in the parent object where this text is located (for easy replacement)
        }|kwargs
        
    def load_data(self, filename):
        filename = Path(filename)
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if not isinstance(item, dict):
                continue
            _data = []
            for field in TRANSLATION_FIELDS.get(filename.stem, []):
                if original := item.get(field, ""):
                    translation = self.translated_mapping.get(original, "")
                    _data.append(self.forge_data(filename.stem, item, field, original, _parent=item, _key=field))
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
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        # make items selectable and enabled; only the Translation column is editable
        col = index.column()
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        try:
            if self._columns[col] == "Translated":
                flags |= Qt.ItemIsEditable
        except Exception:
            pass
        return flags

    def set_translation(self, filtered_row_index: int, text: str):
        # TODO: AI GENERATED: NEED REVIEW
        # Update translation mapping and underlying data for the given filtered row
        if filtered_row_index < 0 or filtered_row_index >= len(self.filtered_data):
            return False
        row = self.filtered_data.iloc[filtered_row_index]
        original = row.get("Original")
        if original is None:
            return False
        # update mapping
        self.translated_mapping[original] = text
        # update all rows in _data where Original equals this original
        mask = self._data["Original"] == original
        self._data.loc[mask, "Translated"] = text
        # clear cached filtered data so callers get fresh view
        self._filtered_data = None
        # emit data changed for the whole model (simple and safe)
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right)
        return True

    def setData(self, index, value, role=Qt.EditRole):
        # Support inline editing from the view for the Translation column
        if role != Qt.EditRole or not index.isValid():
            return False
        row = index.row()
        col = index.column()
        try:
            col_name = self._columns[col]
        except Exception:
            return False
        if col_name != "Translated":
            return False
        text = str(value)
        # locate original value from filtered data
        if row < 0 or row >= len(self.filtered_data):
            return False
        original = self.filtered_data.iloc[row].get("Original")
        if original is None:
            return False
        # update mapping and underlying data
        self.translated_mapping[original] = text
        mask = self._data["Original"] == original
        self._data.loc[mask, "Translated"] = text
        self._filtered_data = None
        self.dataChanged.emit(index, index)
        return True


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

class TranslationTableView(qt.QTableView):
    # TODO: AI GENERATED: NEED REVIEW
    def __init__(self, parent=None):
        super().__init__(parent)
        # Use row selection and single selection so a row is selected at a time
        self.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        # enable custom context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # allow inline editing via double-click or edit key
        self.setEditTriggers(qt.QAbstractItemView.DoubleClicked | qt.QAbstractItemView.EditKeyPressed | qt.QAbstractItemView.SelectedClicked)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            # trigger edit of the selected row's Translation
            sel = self.selectionModel().selectedRows()
            if not sel:
                return
            row = sel[0].row()
            model = self.model()
            if not isinstance(model, TranslationTableModel):
                return
            # start inline editing for the Translation column
            col = model._columns.index("Translation")
            self.edit(model.index(row, col))
            return
        super().keyPressEvent(event)

    def show_context_menu(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        model = self.model()
        if not isinstance(model, TranslationTableModel):
            return
        menu = qt.QMenu(self)
        
        api_action = menu.addAction("Translate with API")
        edit_action = menu.addAction("Edit Translation")
        reset_action = menu.addAction("Reset Translation")
        copy_action = menu.addAction("Copy Original")

        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action == api_action:
            for sel in self.selectionModel().selectedRows():
                row = sel.row()
                original = model.data(model.index(row, model._columns.index("Original")), Qt.DisplayRole)
                if original is not None and (translated:=translate(original)) is not None:
                    model.set_translation(row, translated)
            
        elif action == edit_action:
            current = model.data(model.index(row, model._columns.index("Translation")), Qt.DisplayRole)
            text, ok = qt.QInputDialog.getText(self, "Edit Translation", "Translation:", text=str(current))
            if ok:
                model.set_translation(row, text)
        elif action == reset_action:
            # clear translation for this original
            original = model.data(model.index(row, model._columns.index("Original")), Qt.DisplayRole)
            if original is not None:
                model.set_translation(row, "")
        elif action == copy_action:
            original = model.data(model.index(row, model._columns.index("Original")), Qt.DisplayRole)
            qt.QApplication.clipboard().setText(str(original))

    
# Actors.json: name, nickname, profile
class TranslationApp(qt.QMainWindow):
    def __init__(self, settings_path="settings.json"):
        super().__init__()
        self.settings = Settings.load(settings_path)
        L.set_language(self.settings.language)
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
        
    def initUI(self):
        self.top_bar = self.menuBar()
        self.central_widget = qt.QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = qt.QVBoxLayout(self.central_widget)
        
        self.init_menu_bar()
        
        button_layout = qt.QHBoxLayout()
        filter_button = qt.QPushButton("Filter", self)
        filter_button.clicked.connect(self.open_filter_menu)
        button_layout.addWidget(filter_button)
        
        self.table = TranslationTableView(self)
        self.model = TranslationTableModel([])
        self.debug()  # Load test data # Remove this line in production #TODO
        self.table.setModel(self.model)
        
        self.main_layout.addLayout(button_layout)
        self.main_layout.addWidget(self.table)
        
        for col, width in enumerate(TranslationTableModel._COLWIDTHS):
            self.table.setColumnWidth(col, width)
        # make header stretch for readability
        self.table.horizontalHeader().setStretchLastSection(False)
        
    def init_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu(L["File"])
        file_menu.addMenu(L["menu.file.recentFiles"])
        actions={}
        actions["save_translation"] = qt.QAction(L["menu.file.saveTranslation"], self)
        # actions["load_translation"] = qt.QAction(L["menu.file.load.action"], self)
        actions["save_game_file"] = qt.QAction(L["menu.file.saveGameFile"], self)
        actions["load_game_file"] = qt.QAction(L["menu.file.loadGameFile"], self)
        
        actions["save_translation"].triggered.connect(self.save_translations)
        actions["save_game_file"].triggered.connect(self.save_game_file)
        actions["load_game_file"].triggered.connect(self.load_game_file)
        
        actions["settings"] = qt.QAction(L["menu.settings"], self)
        actions["settings"].triggered.connect(self.open_settings)
        
        for action in actions.values():
            file_menu.addAction(action)
        menubar.addAction(actions["settings"])
        
    def save_translations(self):
        pass #TODO: implement saving translation dictionary to reuse for later sessions
    def load_translations(self): 
        pass #TODO: implement loading translation dictionary from previous sessions to avoid losing work and to reuse translations across similar text in different files
    def load_game_file(self):        pass #TODO: implement loading a game data file (e.g. Actors.json) and extracting translatable text to add to the table for translation
    def save_game_file(self):        pass #TODO: implement saving the game data file with
    
    
    def debug(self):
        with open("test/dictionary.json", "r", encoding="utf-8") as f:
            self.model.translated_mapping = json.load(f)
        # self.model.load_data("test/Actors.json")
        # self.model.load_data("test/Armors.json")
        # self.model.load_data("test/Items.json")
        # self.model.load_data("test/Classes.json")
        # self.model.load_events("test/CommonEvents.json")
        self.model.load_map_data("test/Map001.json")
        # Menu bar actions
        
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_()== qt.QDialog.Accepted:
            dialog.save_settings()
            L.set_language(self.settings.language) #TODO: optimize by only reloading translations if language actually changed
            # TODO: update UI language immediately without needing to restart the app. This requires all UI text to be retrieved from LanguagePack with the current language, and emitting signals to update text when language changes.
            logger.debug("Settings saved")
            # Persist and apply theme immediately
            try:
                self.settings.save()
            except Exception:
                logger.exception("Failed to save settings.json")
            apply_theme_to_app(self.settings.dark_mode)
        else:
            logger.debug("Settings dialog cancelled")
    

def apply_theme_to_app(dark: bool) -> None:
    """Load and apply the dark QSS stylesheet when requested, or clear stylesheet for light mode."""
    
    app = qt.QApplication.instance()
    if app is None:
        return
    # Cast to QApplication so static type checkers know setStyleSheet exists
    app_qt = cast(qt.QApplication, app)
    qss_path = Path(__file__).parent / "styles" / "dark.qss"
    if dark and qss_path.exists():
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                app_qt.setStyleSheet(f.read())
        except Exception as e:
            logger.error(f"Failed to load dark theme {qss_path}: {e}")
    else:
        app_qt.setStyleSheet("")

if __name__ == "__main__":
    app = qt.QApplication([])
    translator = TranslationApp()
    translator.show()
    app.exec_()