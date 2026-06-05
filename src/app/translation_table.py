import pandas as pd
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QAbstractTableModel
from PyQt5.QtGui import QDropEvent, QCursor, QIcon, QColor
from PyQt5.QtWidgets import (
    QTableView, QAbstractItemView, 
    QInputDialog, QMenu, QApplication
)

from app.settings import Settings
from core.text_unit import TextUnit
from translation import Translator, batch_chinese_convertion
from .language import LanguagePack
from .gui.theme import ThemeManager
L = LanguagePack()

class TranslationTableModel(QAbstractTableModel):
    _columns = ["file", "id", "attribute", "original", "translation"]
    _COLWIDTHS = [100, 20, 80, 500, 500]
    
    def __init__(self, data):
        super().__init__()
        self._data:pd.DataFrame = pd.DataFrame(data, columns=self._columns)
        self._filtered_data = None
        self.translated_mapping = {}
        self.translation_levels = {}
        self.filters = {}

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return L[self._columns[section]]
        return section + 1
    
    def load_units(self, units: list[TextUnit]):
        """Load a list of TextUnit objects(dataclass), and convert them into the internal DataFrame format for the model."""
        data = []
        for unit in units:
            data.append(unit)
            self.translated_mapping[unit.id] = unit.translation
            self.translation_levels[unit.id] = "DICTIONARY"  # default level for pre-translated units; can be updated later
        self._data = pd.concat([self._data, pd.DataFrame(data, columns=self._columns)], ignore_index=True)
        self._filtered_data = None

    def set_filters(self, filters):
        # filters: dict of {column: {"text": str, "is_regex": bool}}
        self.filters = filters or {}
        # clear cached filtered data so it will be recalculated
        self._filtered_data = None
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return len(self.filtered_data)

    def build_mask(self, filters):
        # Build boolean mask for all filters (case-insensitive substring match)
        mask = pd.Series([True] * len(self._data), index=self._data.index)
        for col, filter_data in filters.items():
            if col not in self._data.columns:
                continue
            text = filter_data.get("text", "")
            is_regex = filter_data.get("is_regex", False)
            # ensure strings and perform case-insensitive substring match
            mask &= self._data[col].astype(str).str.contains(text, case=False, regex=is_regex, na=False)
        return mask
        
    @property
    def filtered_data(self):
        if not self.filters:
            return self._data
        if self._filtered_data is not None:
            return self._filtered_data

        mask = self.build_mask(self.filters)
        self._filtered_data = self._data[mask].reset_index(drop=True)
        return self._filtered_data

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        theme = ThemeManager.theme
        
        if not index.isValid():
            return None
        r = index.row()
        c = index.column()
        
        if ((role == Qt.BackgroundRole and theme.USE_COLOR_LEVEL_BACKGROUND) or
            (role == Qt.ForegroundRole and not theme.USE_COLOR_LEVEL_BACKGROUND) ):
            if r < 0 or r >= len(self.filtered_data):
                return None
            row = self.filtered_data.iloc[r]
            original = row.original
            # translation = row.translation
            level = self.translation_levels.get(original, None)
            if level is None:
                # level = "UNTRANSLATED" if not str(translation).strip() else "VERIFIED"
                level = "UNTRANSLATED"
            return QColor(ThemeManager.theme.get_level_color(level))
        
        if role == Qt.DisplayRole:
            if r < 0 or r >= len(self.filtered_data):
                return None
            if c < 0 or c >= len(self._columns):
                return None
            row = self.filtered_data.iloc[r]
            col = self._columns[c]
            return row.get(col, "")
        return None

    def _set_level_for_original(self, original: str, level: str):
        if not original:
            return
        self.translation_levels[original] = level

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        # make items selectable and enabled; only the Translation column is editable
        col = index.column()
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        try:
            if self._columns[col] == "translation":
                flags |= Qt.ItemIsEditable
        except Exception:
            pass
        return flags

    def set_translation(self, filtered_row_index: int, text: str, level: str = "VERIFIED"):
        # TODO: AI GENERATED: NEED REVIEW
        # Update translation mapping and underlying data for the given filtered row
        original = self.filtered_data.iloc[filtered_row_index].get("original")
        if original is None:
            return False
        # update mapping
        self.translated_mapping[original] = text
        self._set_level_for_original(original, level if text else "UNTRANSLATED")
        # update all rows in _data where Original equals this original
        mask = self._data["original"] == original
        self._data.loc[mask, "translation"] = text
        # clear cached filtered data so callers get fresh view
        self._filtered_data = None
        # emit data changed for the whole model (simple and safe)
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right)
        return True
    
    def search_and_replace(self, filters: dict, replace_text: str, column: str = "original"):
        """Replace translations based on search criteria. 
        Filters is a dict of {column: {"text": str, "is_regex": bool, "match_case": bool}}.
        Replace_text is a regex pattern or plain text to replace with. Column specifies which column to apply the search and replace on (default "original").
        Returns the number of replacements made.
        """
        if column not in self._data.columns:
            return 0
        mask = self.build_mask(filters)
        if not mask.any():
            return 0
        self._data.loc[mask, "translation"] = self._data.loc[mask, column].str.replace(
            filters[column]["text"], replace_text, regex=filters[column].get("is_regex", False),
        )
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        return mask.sum()
    
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
        if col_name != "translation":
            return False
        text = str(value)
        # locate original value from filtered data
        if row < 0 or row >= len(self.filtered_data):
            return False
        original = self.filtered_data.iloc[row].get("original")
        if original is None:
            return False
        # update mapping and underlying data
        self.translated_mapping[original] = text
        self._set_level_for_original(original, "VERIFIED" if text else "UNTRANSLATED")
        mask = self._data["original"] == original
        self._data.loc[mask, "translation"] = text
        self._filtered_data = None
        self.dataChanged.emit(index, index)
        return True
    
    def chs2cht(self):
        """Convert all Chinese translations from Simplified to Traditional using OpenCC."""
        filtered = self.filtered_data
        if filtered.empty:
            return 
        filtered["translation"] = batch_chinese_convertion(filtered["translation"], target='tw')
        
    def cht2chs(self):
        """Convert all Chinese translations from Simplified to Traditional using OpenCC."""
        filtered = self.filtered_data
        if filtered.empty:
            return
        filtered["translation"] = batch_chinese_convertion(filtered["translation"], target='s')
        
        
    
class TranslationTableView(QTableView):
    # TODO: AI GENERATED: NEED REVIEW
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        # Use row selection and single selection so a row is selected at a time
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # self.setAlternatingRowColors(True)
        # enable custom context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # allow inline editing via double-click or edit key
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        if settings is None:
            settings = Settings()
        self.translator = Translator(settings)
        
    def edit_translation_row(self, row: int, model: TranslationTableModel) -> None:
        current = model.data(model.index(row, model._columns.index("translation")), Qt.DisplayRole)
        text, ok = QInputDialog.getText(self, "Edit Translation", "Translation:", text=str(current))
        if ok:
            model.set_translation(row, text, level="VERIFIED")

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            # edit the selected row using the same dialog as the context menu
            sel = self.selectionModel().selectedRows()
            if not sel:
                return
            row = sel[0].row()
            model = self.model()
            if not isinstance(model, TranslationTableModel):
                return
            self.edit_translation_row(row, model)
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
        menu = QMenu(self)
        
        api_action =   menu.addAction(L['rightClick.translateWithAPI'])
        edit_action =  menu.addAction(L['rightClick.editTranslation'])
        reset_action = menu.addAction(L['rightClick.resetTranslation'])
        copy_action =  menu.addAction(L['rightClick.copyOriginal'])

        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action == api_action:
            for sel in self.selectionModel().selectedRows():
                row = sel.row()
                original = model.data(model.index(row, model._columns.index("original")), Qt.DisplayRole)
                if not isinstance(original, str):
                    return
                if (translated:=self.translator.translate(original)) is not None:
                    model.set_translation(row, translated, level="API")
            
        elif action == edit_action:
            self.edit_translation_row(row, model)
        elif action == reset_action:
            # clear translation for this original
            original = model.data(model.index(row, model._columns.index("original")), Qt.DisplayRole)
            if original is not None:
                model.set_translation(row, "", level="UNTRANSLATED")
        elif action == copy_action:
            original = model.data(model.index(row, model._columns.index("original")), Qt.DisplayRole)
            QApplication.clipboard().setText(str(original))