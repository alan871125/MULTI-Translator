import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, override

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox, QFileDialog, QMainWindow, QTabWidget, QUndoStack, QWidget, 
    QVBoxLayout, QHBoxLayout, 
    QPushButton, QMessageBox,
    QInputDialog, QDialog, QDialogButtonBox,
    QMenu, QShortcut, QComboBox, QAction,
)

from app.gui.dialogs.settings import SettingsDialog
from app.gui.theme import ThemeManager
from app.gui.dialogs.search import TableFilters
from app.models.translation_table_model import TranslationTableModel
from app.translation_table import TranslationTabWidget
from app.language import LanguagePack
from app.settings import Settings
from .menu_utils import initialize_menu
from .dialogs.search import SearchDialog
from .components import TopBar, BottomPanel, RecentFilesMenu
import core.engines as engines

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
L = LanguagePack()

from ..translation_table import EditType 


    
class TranslationApp(QMainWindow):
    edit_current_file_requested = pyqtSignal(EditType)
    save_current_file_requested = pyqtSignal(str)
    save_translation_requested = pyqtSignal()
    load_file_requested = pyqtSignal(str)
    
    def __init__(self, settings: Settings, filters: TableFilters):
        super().__init__()
        self._current_undo_stack = None
        self.settings = settings
        self.filters = filters
        L.set_language(self.settings.language)
        ThemeManager().set_theme(dark = settings.dark_mode) # Apply theme based on settings at startup
        # 1. Inintialize UI
        self.setWindowTitle("RPG Translator")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)
        
        # Initialize the undo/redo actions first to be added and linked
        self.undo_action = QAction("Undo", self) 
        self.redo_action = QAction("Redo", self)
        self.undo_action.triggered.connect(lambda: self._current_undo_stack and self._current_undo_stack.undo())
        self.redo_action.triggered.connect(lambda: self._current_undo_stack and self._current_undo_stack.redo())
        
        self.init_ui()
        self.init_hotkeys()
        # 2. Register callbacks
        self.settings.setting_changed.connect(self.lru_menu.refresh)  # Refresh recent files menu when settings change
        
        
    @override
    def closeEvent(self, event):
        # save the current state of the application
        open_tabs = self.translation_table.tabs.keys()
        self.settings.last_open_tabs = open_tabs
        self.settings.last_open_workspace = self.settings.workspace_dir
        self.settings.save()
        super().closeEvent(event)

    def open_filter_menu(self):
        # Popup a filter Menu with Column: entries for columns in the table.
        if (model := self.translation_table.currentModel()) is None:
            logger.warning("No active translation tab to apply filters to.")
            return
        dialog = SearchDialog(self.filters, self)
        dialog.replace_requested.connect(model.search_and_replace)  # Connect the replace signal to the model's replace method
        # Hide the replace button (hidden when only filtering)
        dialog.replace_widget.setVisible(False)  
        dialog.exec_()
        # Apply the filters to the table model
        dialog.set_filters()
        
    def init_ui(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 1. Top Bar
        self.top_bar = TopBar(self.settings, self.filters)
        self.top_bar.filter_clicked.connect(self.open_filter_menu)
        self.top_bar.workspace_clicked.connect(self.open_load_workspace_dialog)
        
        # 2. Translation Table
        self.translation_table = TranslationTabWidget(self.filters)
        self.translation_table.setTabsClosable(True)
        # self.translation_table.tabCloseRequested.connect(self.translation_table.removeTab)

        self.init_menu_bar()
        
        # 4. Bottom Panel
        # self.bottom_panel = BottomPanel(L, self)
        
        self.main_layout.addWidget(self.top_bar)
        self.main_layout.addWidget(self.translation_table)
        # self.main_layout.addWidget(self.bottom_panel)
        
    def init_menu_bar(self):
        self.lru_menu = RecentFilesMenu(L["menu.file.recent_files"], self.settings.recent_files)
        menu_def = {
            "file.load_game_file": self.open_load_file_dialog,
            "file.load_workspace": self.open_load_workspace_dialog,
            # "file.new_workspace": self.open_load_workspace_dialog,
            "file.save_translation": self.save_translation_requested.emit,
            "file.recent_files": self.lru_menu,
            "file.save_game_file": lambda :self.save_current_file_requested.emit("{default}"),
            "file.save_game_file_as": lambda :self.save_current_file_requested.emit("{custom}"),
            "settings": self.open_settings,
            "edit.undo": self.undo_action,
            "edit.redo": self.redo_action,
            "tools.chinese_conversion.chs2cht": lambda: self.edit_current_file_requested.emit(EditType.CHS2CHT),
            "tools.chinese_conversion.cht2chs": lambda: self.edit_current_file_requested.emit(EditType.CHT2CHS),
        } 
        menus = initialize_menu(menu_def, self.menuBar(), root_menu_name="menu", tr=L.__getitem__)
        menus["file.save_translation"].setEnabled(False)  # Disable save translation action until a tab is loaded with a file
        self.translation_table.tab_exist_signal.connect(lambda exist: menus["file.save_translation"].setEnabled(exist))  # Enable save action only when a tab with a loaded file exists
        self.lru_menu.recent_file_selected.connect(self.load_file_requested.emit)  # Connect recent file selection to load file signal
        
    def init_hotkeys(self):
        self.hotkeys = {
            "save": QShortcut(Qt.CTRL + Qt.Key_S, self),
            "search": QShortcut(Qt.CTRL + Qt.Key_F, self),
        }
        self.hotkeys["save"].activated.connect(self.save_translation_requested.emit)
        self.hotkeys["save"].setEnabled(False)  # Disable save hotkey until a tab with a loaded file exists
        self.hotkeys["search"].activated.connect(self.open_filter_menu)
        self.translation_table.tab_exist_signal.connect(lambda exist:self.hotkeys["save"].setEnabled(exist))

        self.undo_action.setShortcuts(QKeySequence.Undo)   
        self.redo_action.setShortcuts(QKeySequence.Redo) 
        self.addAction(self.undo_action) # Ctrl+Z / Cmd+Z
        self.addAction(self.redo_action) # Ctrl+Y / Cmd+Shift+Z
    
    def bind_undo_redo_actions(self, stack: Optional[QUndoStack]):
        if self._current_undo_stack is stack:
            return
            
        if self._current_undo_stack is not None:
            try:
                # Disconnect logic signals
                self._current_undo_stack.canUndoChanged.disconnect(self.undo_action.setEnabled)
                self._current_undo_stack.canRedoChanged.disconnect(self.redo_action.setEnabled)
            except (TypeError, RuntimeError):
                # This is expected when the stack was destroyed after closing a tab
                pass
        
        self._current_undo_stack = stack
        if stack:
            # Connect logic signals
            stack.canUndoChanged.connect(self.undo_action.setEnabled)
            stack.canRedoChanged.connect(self.redo_action.setEnabled)
            # Update initial state
            self.undo_action.setEnabled(stack.canUndo())
            self.redo_action.setEnabled(stack.canRedo())
        else:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
        
    def open_load_workspace_dialog(self):
        workspace_dir = QFileDialog.getExistingDirectory(self, L["FileDialoge.select_workspace_dir"], "")
        if workspace_dir:
            self.settings.update_workspace(workspace_dir) # Load the selected workspace using the settings manager, which will also update recent files and refresh the top bar through signals
            
    def open_load_file_dialog(self):
        extractor = engines.extractors[self.settings.engine]()
        supported_types = extractor.SUPPORTED_FILES_TYPES
        file_filters = ";;".join(f"{ft.upper()} Files (*{ft})" for ft in supported_types)+f";;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(self, L["file_dialog.select_game_file"], "", file_filters)
        if not file_path:
            return  # User cancelled the file dialog
        self.load_file_requested.emit(file_path)  # Emit the signal to load the file, which will be handled by the presenter

    def open_edit_translation_dialog(self, current_text: str) -> Optional[str]:
        text, ok = QInputDialog.getText(self, "Edit Translation", "Translation:", text=current_text)
        if ok:
            return text
        return None

    def show_share_translation_confirmation(self)-> bool:
        # Display the confirmation box
        if confirm:=(self.settings.confirmations.share_translation) is not None:
            # User chose to not show again, use the saved preference
            return confirm
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Confirm Action")
        msg_box.setText(L["confirm_msg.share_translation"])
        check_box = QCheckBox(L["confirm_msg.dont_ask_again"])
        msg_box.setCheckBox(check_box)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        # Handle user selection
        result = (msg_box.exec()==QMessageBox.StandardButton.Yes)
        if check_box.isChecked():
            self.settings['confirmations.share_translation'] = result
        return result
    
    def open_save_game_file_dialog(self, default_file_path: str) -> Optional[str]:
        # if (model := self.translation_table.currentModel()) is None:
        #     logger.warning("No active translation tab to save.")
        #     return
        # current_file = model.file_path
        # default_name = current_file.name if current_file else "translated_file.json"
        save_path, _ = QFileDialog.getSaveFileName(
            self, L["file_dialog.save_translated_file"], default_file_path, 
            "JSON Files (*.json);;All Files (*.*)"
        )
        if not save_path:
            return  # User cancelled the save dialog
        return save_path
    
    # def save_game_file(self):        
    #     if (model := self.translation_table.currentModel()) is None:
    #         logger.warning("No active translation tab to save.")
    #         return
    #     try:
    #         model.save_to_game_file()
    #         # TODO: Implement the status bar
    #         self.statusBar().showMessage(L["statusBar.saved_success"], 3000)
    #     except Exception as e:
    #         logger.exception(f"Failed to save game file: {e}")
    #         QMessageBox.critical(self, "Save Error", f"Could not save game file:\n{e}")
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_()== QDialog.Accepted:
            dialog.save_settings()
            L.set_language(self.settings.language)
            logger.debug("Settings saved")
            try:
                self.settings.save()
            except Exception:
                logger.exception("Failed to save settings.json")
            ThemeManager().set_theme(dark = self.settings.dark_mode)
        else:
            logger.debug("Settings dialog cancelled")

