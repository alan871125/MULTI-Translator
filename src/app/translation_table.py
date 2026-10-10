import logging
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Generic, TypeVar, override
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractItemModel, QAbstractProxyModel
from PySide6.QtGui import QDropEvent, QKeySequence, QKeyEvent, QShortcut, QIcon
from PySide6.QtWidgets import (
    QWidget, QTabWidget, QTableView, QAbstractItemView, 
    QMenu, QApplication, 
    QToolButton, QTabBar
)
from qt_extensions.core import TypedSignal
from iod import IndexedOrderedDict
from core.translation import TranslationLevel, TranslationDictionary
from .language import LanguagePack
from .models.translation_table_model import TranslationTableModel
from .typing import IndexLikeSequence
logger = logging.getLogger(__name__)
L = LanguagePack()

class EditType(Enum):
    API = "api"
    API_BATCH = "api_batch"
    MANUAL = "manual"
    RESET = "reset"
    SHARE = "share"
    PASTE = "paste"
    LEVEL = "level"
    CHS2CHT = "chs2cht"
    CHT2CHS = "cht2chs"
    SHARE_TOP_LV = "share_top_lv" #TODO: possibly move this elsewhere
T = TypeVar("T", bound=EditType)
@dataclass(slots=True)
class TranslationRequest(Generic[T]):
    rtype: T
    row_idxs: IndexLikeSequence
    val: Optional[TranslationLevel|str] = None
    # col: Optional[int|str] = None

class TranslationTableView(QTableView):
    _COLWIDTHS = [60, 80, 500, 500]
    edit_translation_requested = TypedSignal(TranslationRequest)
    copy_cells_requested = TypedSignal(IndexLikeSequence, int)  # row indexes, column index (only support single column for now)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Use row selection and single selection so a row is selected at a time
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # self.setAlternatingRowColors(True)
        # enable custom context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # allow inline editing via double-click or edit key
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | 
            # QAbstractItemView.EditKeyPressed | # F2 conflicts with level setting hotkeys.
            QAbstractItemView.EditTrigger.SelectedClicked
        ) 
        # horizontal header left align and stretch last section
        h_header = self.horizontalHeader()
        h_header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        h_header.setStretchLastSection(True)
        self.init_hotkeys()
        self.proxy_model: Optional[QAbstractProxyModel] = None

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
        if self.proxy_model is None:
            return [index.row() for index in sel]
        return [self.proxy_model.mapToSource(index).row() for index in sel]
    
    @property
    def selected_source_indexes(self) ->IndexLikeSequence:
        """Returns the source model row indexes of the currently selected rows in the view."""        
        if (
            self.proxy_model is None or 
            not isinstance(model := self.proxy_model.sourceModel(), TranslationTableModel)
        ):
            return self.selected_source_rows
        return model.df.index[self.selected_source_rows].to_list()
    @override
    def setModel(self, model:Optional[QAbstractItemModel]):
        super().setModel(model)
        if isinstance(model, QAbstractProxyModel):
            self.proxy_model = model
            self.setSortingEnabled(True)
            self.set_column_widths(self._COLWIDTHS)
    
    @override
    def keyPressEvent(self, e:QKeyEvent):
        key = e.key()
        sequence = QKeySequence(e.modifiers().value | e.key())
        idxs = self.selected_source_indexes
        if len(idxs) > 0 and sequence.matches(QKeySequence.StandardKey.Paste)==QKeySequence.SequenceMatch.ExactMatch:
            # self.edit_translation_requested.emit(idxs, EditType.PASTE)
            self.edit_translation_requested.emit(TranslationRequest(EditType.PASTE, idxs))
        elif len(idxs) > 0 and sequence.matches(QKeySequence.StandardKey.Copy)==QKeySequence.SequenceMatch.ExactMatch:
            col = self.selectionModel().currentIndex().column()
            self.copy_cells_requested.emit(idxs, col)  # Emit the column index of the selected cell
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # If currently inline editing, let the view handle the enter key (usually commits the edit)
            if self.state() == QAbstractItemView.State.EditingState:
                return super().keyPressEvent(e)
            if not idxs:
                return super().keyPressEvent(e)
            # Removed the check for model type here, as we want to allow editing regardless of the model type. The model should handle whether editing is allowed or not.
            # model = self.model()
            # if not isinstance(model, TranslationTableModel):
            #     return super().keyPressEvent(e)
            self.edit_translation_requested.emit(TranslationRequest(EditType.MANUAL, idxs[:1]))
            return
        else:
            super().keyPressEvent(e)

    def set_column_widths(self, colwidths: list[int]):
        for i, width in enumerate(colwidths):
            self.setColumnWidth(i, width)

    def show_context_menu(self, pos):
        idx = self.indexAt(pos)
        if self.proxy_model is not None:
            idx = self.proxy_model.mapToSource(idx)
        if not idx.isValid():
            return
        
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
        translate_as_batch_action = menu.addAction(L['right_click.translate_as_batch'])

        # Execute the menu at the cursor position and get the selected action
        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action is None:
            return
        # idxs = self.selected_source_rows
        idxs = self.selected_source_indexes
        if action == api_action:
            self.edit_translation_requested.emit(TranslationRequest(EditType.API, idxs))
        elif action == edit_action:
            self.edit_translation_requested.emit(TranslationRequest(EditType.MANUAL, idxs))
        elif action == reset_action:
            self.edit_translation_requested.emit(TranslationRequest(EditType.RESET, idxs))
        elif action == copy_action:
            original = model.data(model.index(idx.row(), model._COLUMNS.index("original")), Qt.ItemDataRole.DisplayRole)
            QApplication.clipboard().setText(str(original))
        elif action == translate_as_batch_action:
            self.edit_translation_requested.emit(TranslationRequest(EditType.API_BATCH, idxs))

    def on_level_hotkey_triggered(self, level: TranslationLevel):
        if (idxs := self.selected_source_indexes):
            self.edit_translation_requested.emit(TranslationRequest(EditType.LEVEL, idxs, val=level))

class DynamicCloseButton(QToolButton):
    """A QToolButton that changes its icon based on the save status of the associated tab."""
    ICON = QIcon(":/assets/resources/icons/close.svg")
    ICON_ALT = QIcon(":/assets/resources/icons/close-unsaved.svg")
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoRaise(True) # Makes it look like a flat button without borders
        self.switch_icon(True)  # Default to saved state
        
    def switch_icon(self, alt: bool):
        self.setIcon(self.ICON if alt else self.ICON_ALT)
        
class TranslationTabWidget(QTabWidget):
    """A QTabWidget that manages multiple TranslationTableViews, each associated with a translation file.  
    
    It keeps track of the open tabs and their corresponding file paths, 
    provides signals for when tabs are added or removed, as well as when the current tab changes."""
    tab_exist_signal = TypedSignal(bool)  # file_name
    tab_save_signal = TypedSignal(str)  # file_name
    open_dropped_file_request = TypedSignal(str)  # file_path
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
    def currentWidget(self) -> TranslationTableView:
        widget = super().currentWidget()
        if not isinstance(widget, TranslationTableView):
            logger.warning("Current widget is not a TranslationTableView: %s", type(widget))
            raise TypeError("Current widget is not a TranslationTableView")
        return widget
    @override
    def dragEnterEvent(self, a0:QDropEvent):
        if a0.mimeData().hasUrls():
            a0.accept()
        else:
            a0.ignore()
    @override
    def dropEvent(self, a0:QDropEvent):
        for url in a0.mimeData().urls():
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
        index = self.addTab(new_tab, Path(file_path).name)
        self.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, DynamicCloseButton(self))
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
    
    def update_tab_save_status(self, file_path: str, clean: Optional[bool] = None):
        if file_path not in self.tabs:
            return
        index = self.indexOf(self.tabs[file_path])
        if index == -1:
            return
        current_title = self.tabText(index)
        close_button = self.tabBar().tabButton(index, QTabBar.ButtonPosition.RightSide)
        
        if clean is False:
            if not current_title.endswith("*"):
                self.setTabText(index, current_title + "*")
            if close_button and isinstance(close_button, DynamicCloseButton):
                close_button.switch_icon(False)
        else:
            if current_title.endswith("*"):
                self.setTabText(index, current_title[:-1])
            if close_button and isinstance(close_button, DynamicCloseButton):
                close_button.switch_icon(True)