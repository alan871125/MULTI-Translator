import logging
import pandas as pd
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Sequence, override, Generic, TypeVar

from PyQt5.QtCore import Qt, QSortFilterProxyModel
from PyQt5.QtGui import QDropEvent, QKeySequence
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QShortcut, QTabWidget, QTableView, QAbstractItemView, QCheckBox,
    QInputDialog, QMenu, QApplication, QWidget, QTabBar
)
from qt_utils import TypedQtSignal
from iod import IndexedOrderedDict
from config import settings
from core.translation import TranslationLevel, TranslationDictionary, Translator
from .language import LanguagePack
from .models.filters import TableFilters
from .models.translation_table_model import CaseInsensitiveSortProxyModel, TranslationTableModel, TranslationTableProxyModel
logger = logging.getLogger(__name__)
L = LanguagePack()

class EditType(Enum):
    API = "api"
    MANUAL = "manual"
    RESET = "reset"
    SHARE = "share"
    PASTE = "paste"
    LEVEL = "level"
    CHS2CHT = "chs2cht"
    CHT2CHS = "cht2chs"

T = TypeVar("T", bound=EditType)
@dataclass(slots=True)
class TranslationRequest(Generic[T]):
    rtype: T
    row_idxs: list[int]|pd.Index
    val: Optional[TranslationLevel|str] = None
    # col: Optional[int|str] = None

class TranslationTableView(QTableView):
    _COLWIDTHS = [60, 80, 500, 500]
    edit_translation_requested = TypedQtSignal(TranslationRequest)
    # set_level_requested = TypedQtSignal(list, TranslationLevel)  # row indexes, level
    copy_cells_requested = TypedQtSignal(list, int)  # row indexes, column index (only support single column for now)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Use row selection and single selection so a row is selected at a time
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # self.setAlternatingRowColors(True)
        # enable custom context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # allow inline editing via double-click or edit key
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked | 
            # QAbstractItemView.EditKeyPressed | # F2 conflicts with level setting hotkeys.
            QAbstractItemView.SelectedClicked  #
        ) 
        # horizontal header left align and stretch last section
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.horizontalHeader().setStretchLastSection(True)
        self.init_hotkeys()

    def init_hotkeys(self):
        # F1~F6 to set translation level for selected rows
        for i, level in enumerate(TranslationLevel, start=1):
            hotkey = QShortcut(QKeySequence(f"F{i}"), self)
            hotkey.activated.connect(
                lambda lvl=level: self.on_level_hotkey_triggered(lvl)
            )
    
    @property
    def selected_source_rows(self)  -> list[int]:
        """Returns the source model row indexes of the currently selected rows in the view."""
        sel = self.selectionModel().selectedRows()
        return self.proxy_model.get_true_indexes(sel, int)
    
    @override
    def setModel(self, model: TranslationTableProxyModel):
        super().setModel(model)
        self.proxy_model = model
        self.setSortingEnabled(True)
        self.set_column_widths(self._COLWIDTHS)

    @override
    def keyPressEvent(self, event):
        key = event.key()
        sequence = QKeySequence(event.modifiers() | key)
        idxs = self.selected_source_rows
        if sequence.matches(QKeySequence.Paste) and len(idxs) > 0:
            # self.edit_translation_requested.emit(idxs, EditType.PASTE)
            self.edit_translation_requested.emit(TranslationRequest(EditType.PASTE, idxs))
        if sequence.matches(QKeySequence.Copy) and len(idxs) > 0:
            col = self.selectionModel().currentIndex().column()
            self.copy_cells_requested.emit(idxs, col)  # Emit the column index of the selected cell
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            # If currently inline editing, let the view handle the enter key (usually commits the edit)
            if self.state() == QAbstractItemView.EditingState:
                return super().keyPressEvent(event)
            if not idxs:
                return super().keyPressEvent(event)
            model = self.model()
            if not isinstance(model, TranslationTableModel):
                return super().keyPressEvent(event)
            self.edit_translation_requested.emit(TranslationRequest(EditType.MANUAL, [idxs[0]]))
            return
        else:
            super().keyPressEvent(event)
            
    def set_column_widths(self, colwidths: list[int]):
        for i, width in enumerate(colwidths):
            self.setColumnWidth(i, width)

    def show_context_menu(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return
        row = self.proxy_model.mapToSource(idx).row()
        model = self.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()
        if not isinstance(model, TranslationTableModel):
            return
        menu = QMenu(self)
        
        api_action =   menu.addAction(L['right_click.translate_with_api'])
        edit_action =  menu.addAction(L['right_click.edit_translation'])
        reset_action = menu.addAction(L['right_click.reset_translation'])
        copy_action =  menu.addAction(L['right_click.copy_original'])

        # Execute the menu at the cursor position and get the selected action
        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if action is None:
            return
        idxs = self.selected_source_rows
        if action == api_action:
            self.edit_translation_requested.emit(TranslationRequest(EditType.API, idxs))
        elif action == edit_action:
            self.edit_translation_requested.emit(TranslationRequest(EditType.MANUAL, idxs))
        elif action == reset_action:
            self.edit_translation_requested.emit(TranslationRequest(EditType.RESET, idxs))
        elif action == copy_action:
            original = model.data(model.index(row, model._COLUMNS.index("original")), Qt.DisplayRole)
            QApplication.clipboard().setText(str(original))

    def on_level_hotkey_triggered(self, level: TranslationLevel):
        if (idxs := self.selected_source_rows):
            self.edit_translation_requested.emit(TranslationRequest(EditType.LEVEL, idxs, val=level))
    
class TranslationTabWidget(QTabWidget):
    """A QTabWidget that manages multiple TranslationTableViews, each associated with a translation file.  
    
    It keeps track of the open tabs and their corresponding file paths, 
    provides signals for when tabs are added or removed, as well as when the current tab changes."""
    tab_exist_signal = TypedQtSignal(bool)  # file_name
    tab_save_signal = TypedQtSignal(str)  # file_name
    open_dropped_file_request = TypedQtSignal(str)  # file_path
    def __init__(self, parent:Optional[QWidget]=None):
        super().__init__(parent)
        self.tabs: IndexedOrderedDict[str, TranslationTableView] = IndexedOrderedDict()  # file_name -> TranslationTableView
        self.dictionaries: IndexedOrderedDict[str, TranslationDictionary] = IndexedOrderedDict()  # file_name -> TranslationDictionary
        self.setAcceptDrops(True)
    # ---------- Overrides ----------
    @override
    def removeTab(self, index: int):
        if index < 0 or index >= self.count():
            return
        key = self.tabs.keys()[index]
        self.tabs.pop(key)  # Remove from the tabs dict based on index
        super().removeTab(index)
        logger.debug("Tab removed: %s, %d remaining", key, len(self.tabs))
        if not self.tabs:            
            self.tab_exist_signal.emit(False)
    @override
    def currentWidget(self) -> Optional[TranslationTableView]:
        widget = super().currentWidget()
        if not isinstance(widget, TranslationTableView):
            logger.warning("Current widget is not a TranslationTableView: %s", type(widget))
            return None
        return widget
    @override
    def dragEnterEvent(self, event:QDropEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    @override
    def dropEvent(self, event:QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if not Path(file_path).exists():
                continue
            self.open_dropped_file_request.emit(file_path)
        
    # ---------- END of Overrides ----------
    
    def currentModel(self) -> Optional[TranslationTableModel]:
        if not (current_widget := self.currentWidget()):
            return None
        model = current_widget.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()
        if isinstance(model, TranslationTableModel):
            return model
        return None
    
    def add_translation_tab(self, file_path: str) -> TranslationTableView:
        if file_path in self.tabs:
            return self.tabs[file_path]
        new_tab = TranslationTableView(self)
        self.tabs[file_path] = new_tab
        self.addTab(new_tab, Path(file_path).name)
        self.tab_exist_signal.emit(True)
        self.setCurrentWidget(new_tab)
        return new_tab
    
    def focus_tab(self, file_path: str):
        if file_path not in self.tabs:
            return
        index = self.indexOf(self.tabs[file_path])
        if index != -1:
            self.setCurrentIndex(index)
    
    def get_current_file_path(self) -> Optional[str]:
        """Returns the file path associated with the currently active tab, or None if no tabs are open."""
        current_widget = self.currentWidget()
        if current_widget is None:
            return None
        index = self.indexOf(current_widget)
        if index == -1:
            return None
        return self.tabs.keys()[index]
    
    def update_tab_save_status(self, file_path: str):
        """Updates the tab title and close button to indicate whether there are unsaved changes."""
        logger.debug("Updating tab save status for %s", file_path)
        if file_path not in self.tabs:
            return
        index = self.indexOf(self.tabs[file_path])
        if index == -1:
            return
        
        model = self.tabs[file_path].model()
        if not isinstance(model, TranslationTableModel) or model.undo_stack is None:
            return
        unsaved = not model.undo_stack.isClean()
        
        # Update tab text (asterisk)
        current_title = self.tabText(index)
        if unsaved:
            if not current_title.endswith("*"):
                self.setTabText(index, current_title + "*")
        else:
            if current_title.endswith("*"):
                self.setTabText(index, current_title[:-1])
