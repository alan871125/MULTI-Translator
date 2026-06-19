import logging
from enum import Enum
from pathlib import Path
from typing import Optional, override

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDropEvent, QKeySequence
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QShortcut, QTabWidget, QTableView, QAbstractItemView, QCheckBox,
    QInputDialog, QMenu, QApplication, QWidget, QTabBar
)
from iod import IndexedOrderedDict
from config import settings
from core.translation import TranslationLevel, TranslationDictionary, Translator
from .language import LanguagePack
from .models.filters import TableFilters
from .models.translation_table_model import TranslationTableModel

logger = logging.getLogger(__name__)
L = LanguagePack()

class EditType(Enum):
    API = "api"
    MANUAL = "manual"
    RESET = "reset"
    SHARE = "share"
    PASTE = "paste"
    CHS2CHT = "chs2cht"
    CHT2CHS = "cht2chs"

class TranslationTableView(QTableView):
    _COLWIDTHS = [60, 80, 500, 500]
    edit_translation_requested = pyqtSignal(list, EditType)  # row indexes, edit type
    copy_cells_requested = pyqtSignal(list, int)  # row indexes, column index (only support single column for now)
    set_level_requested = pyqtSignal(list, TranslationLevel)  # row indexes, level
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

    @override
    def setModel(self, model):
        super().setModel(model)
        self.set_column_widths(self._COLWIDTHS)

    @override
    def keyPressEvent(self, event):
        key = event.key()
        sequence = QKeySequence(event.modifiers() | key)
        rows = self.selectionModel().selectedRows()
        if sequence.matches(QKeySequence.Paste):
            if len(rows) > 0:
                idxs = [idx.row() for idx in rows]
                self.edit_translation_requested.emit(idxs, EditType.PASTE)
        if sequence.matches(QKeySequence.Copy):
            col = self.selectionModel().currentIndex().column()
            if len(rows) != 0:
                idxs = [idx.row() for idx in rows]
                self.copy_cells_requested.emit(idxs, col)  # Emit the column index of the selected cell
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            # If currently inline editing, let the view handle the enter key (usually commits the edit)
            if self.state() == QAbstractItemView.EditingState:
                return super().keyPressEvent(event)
            if not rows:
                return super().keyPressEvent(event)
            row = rows[0].row()
            model = self.model()
            if not isinstance(model, TranslationTableModel):
                return super().keyPressEvent(event)
            self.edit_translation_requested.emit([row], EditType.MANUAL)
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
        row = idx.row()
        model = self.model()
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
        rows = self.selectionModel().selectedRows()
        idxs = [idx.row() for idx in rows]
        if action == api_action:
            self.edit_translation_requested.emit(idxs, EditType.API)
        elif action == edit_action:
            self.edit_translation_requested.emit(idxs, EditType.MANUAL)
        elif action == reset_action:
            self.edit_translation_requested.emit(idxs, EditType.RESET)
        elif action == copy_action:
            original = model.data(model.index(row, model._COLUMNS.index("original")), Qt.DisplayRole)
            QApplication.clipboard().setText(str(original))

    def on_level_hotkey_triggered(self, level: TranslationLevel):
        sel = self.selectionModel().selectedRows()
        if not sel:
            return
        idxs = [idx.row() for idx in sel]
        self.set_level_requested.emit(idxs, level)
    
    
    
class TranslationTabWidget(QTabWidget):
    """A QTabWidget that manages multiple TranslationTableViews, each associated with a translation file.  
    
    It keeps track of the open tabs and their corresponding file paths, 
    provides signals for when tabs are added or removed, as well as when the current tab changes."""
    tab_exist_signal = pyqtSignal(bool)  # file_name
    tab_save_signal = pyqtSignal(str)  # file_name
    open_dropped_file_request = pyqtSignal(str)  # file_path
    def __init__(self, table_filters:TableFilters, parent:Optional[QWidget]=None):
        super().__init__(parent)
        self.table_filters = table_filters
        self.tabs: IndexedOrderedDict[str, TranslationTableView] = IndexedOrderedDict()  # file_name -> TranslationTableView
        self.dictionaries: IndexedOrderedDict[str, TranslationDictionary] = IndexedOrderedDict()  # file_name -> TranslationDictionary
        self.setAcceptDrops(True)
    # ---------- Overrides ----------
    @override
    def addTab(self, widget: TranslationTableView, title: str): 
        # Type hinting for the widget parameter to ensure it's a TranslationTableView, which allows us to access its model and other specific methods if needed in the future.
        assert isinstance(widget, TranslationTableView), "Only TranslationTableView instances can be added to TranslationTabWidget"
        super().addTab(widget, title)
        self.tab_exist_signal.emit(True)
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
        if not isinstance(model, TranslationTableModel):
            return None
        return model
    
    def add_translation_tab(self, file_path: str) -> TranslationTableView:
        if file_path in self.tabs:
            return self.tabs[file_path]
        new_tab = TranslationTableView(self)
        self.tabs[file_path] = new_tab
        self.addTab(new_tab, Path(file_path).name)
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
