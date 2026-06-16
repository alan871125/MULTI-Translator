import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog, QMainWindow, QTabWidget, QWidget, 
    QVBoxLayout, QHBoxLayout, 
    QPushButton, QMessageBox,
    QInputDialog, QDialog, QDialogButtonBox,
    QMenu, QShortcut, QComboBox, QAction,
)

from app.gui.theme import ThemeManager
from app.gui.search import TableFilters
from app.translation_table import TranslationTableModel, TranslationTabWidget
from app.language import LanguagePack
from app.settings import Settings, SettingsDialog
from .menu import initialize_menu
from .search import SearchDialog
from .components import TopBar, BottomPanel, RecentFilesMenu
import engines

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
L = LanguagePack()

    
class TranslationApp(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        L.set_language(self.settings.language)
        ThemeManager().set_theme(dark = settings.dark_mode) # Apply theme based on settings at startup
        # 0. Initialize shared object
        self.filter_manager = TableFilters()  # Create a shared TableFilters instance that can be accessed by all components that need it
        # 1. Inintialize UI
        self.setWindowTitle("RPG Translator")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)
        self.init_ui()
        self.init_hotkeys()
        # 2. Register callbacks
        self.settings.setting_changed.connect(self.lru_menu.refresh)  # Refresh recent files menu when settings change
        
        # 3. Post-initialization actions: Restore session
        if self.settings.restore_last_session:
            self.restore_session()
        
    def closeEvent(self, event):
        # save the current state of the application
        open_tabs = self.translation_table.tabs.keys()
        self.settings.last_open_tabs = open_tabs
        self.settings.last_open_workspace = self.settings.workspace_dir
        self.settings.save()
        super().closeEvent(event)
    
    def restore_session(self):
        # Load previous workspace
        self.settings.load_last_open_workspace()
        # Load the previously open tabs from settings and attempt to restore them
        for file_path in self.settings.last_open_tabs:
            if Path(file_path).exists():
                self.load_game_file(file_path)
            else:
                logger.warning(f"Previously open file {file_path} not found. Skipping.")
        
    def open_filter_menu(self):
        # Popup a filter Menu with Column: entries for columns in the table.
        if (model := self.translation_table.currentModel()) is None:
            logger.warning("No active translation tab to apply filters to.")
            return
        dialog = SearchDialog(self.filter_manager, self)
        dialog.replace_signal.connect(model.search_and_replace)  # Connect the replace signal to the model's replace method
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
        self.top_bar = TopBar(self.settings, self.filter_manager)
        self.top_bar.filter_clicked.connect(self.open_filter_menu)
        self.top_bar.workspace_clicked.connect(self.load_workspace_dialog)
        
        # 2. Translation Table
        self.translation_table = TranslationTabWidget(self.filter_manager)
        self.translation_table.setTabsClosable(True)
        self.translation_table.tabCloseRequested.connect(self.translation_table.removeTab)

        self.init_menu_bar()
        
        # 4. Bottom Panel
        # self.bottom_panel = BottomPanel(L, self)
        
        self.main_layout.addWidget(self.top_bar)
        self.main_layout.addWidget(self.translation_table)
        # self.main_layout.addWidget(self.bottom_panel)
        
    def init_menu_bar(self):
        self.lru_menu = RecentFilesMenu(L["menu.file.recent_files"], self.settings.recent_files)
        menu_def = {
            "file.load_game_file": self.load_game_file_dialog,
            "file.load_workspace": self.load_workspace_dialog,
            "file.new_workspace": self.load_workspace_dialog,
            "file.save_translation": self.translation_table.save_current_tab,
            "file.recent_files": self.lru_menu,
            "file.save_game_file": self.save_game_file,
            "file.save_game_file_as": self.save_game_file_dialog,
            "settings": self.open_settings,
            "edit.undo": None,  # Placeholder for undo action
            "edit.redo": None,  # Placeholder for redo action
            "tools.chinese_conversion.chs2cht": self.translation_table.chs2cht_current_tab,
            "tools.chinese_conversion.cht2chs": self.translation_table.cht2chs_current_tab,
        } 
        menus = initialize_menu(menu_def, self.menuBar(), root_menu_name="menu", tr=L.__getitem__)
        menus["file.save_translation"].setEnabled(False)  # Disable save translation action until a tab is loaded with a file
        self.translation_table.tab_exist_signal.connect(lambda exist: menus["file.save_translation"].setEnabled(exist))  # Enable save action only when a tab with a loaded file exists

    def init_hotkeys(self):
        self.hotkeys = {
            "save": QShortcut(Qt.CTRL + Qt.Key_S, self),
            "search": QShortcut(Qt.CTRL + Qt.Key_F, self),
        }
        self.hotkeys["save"].activated.connect(self.translation_table.save_current_tab)
        self.hotkeys["save"].setEnabled(False)  # Disable save hotkey until a tab with a loaded file exists
        self.hotkeys["search"].activated.connect(self.open_filter_menu)
        self.translation_table.tab_exist_signal.connect(lambda exist:self.hotkeys["save"].setEnabled(exist))

    def load_workspace_dialog(self):
        workspace_dir = QFileDialog.getExistingDirectory(self, L["FileDialoge.select_workspace_dir"], "")
        if workspace_dir:
            self.settings.update_workspace(workspace_dir) # Load the selected workspace using the settings manager, which will also update recent files and refresh the top bar through signals
            
    def load_game_file_dialog(self):
        extractor = engines.extractors[self.settings.engine]()
        supported_types = extractor.SUPPORTED_FILES_TYPES
        file_filters = ";;".join(f"{ft.upper()} Files (*{ft})" for ft in supported_types)+f";;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(self, L["file_dialog.select_game_file"], "", file_filters)
        if not file_path:
            return  # User cancelled the file dialog
        self.load_game_file(file_path)
        
    def load_game_file(self, file_path: str|Path):
        file_path = Path(file_path).absolute()
        try:
            extractor = engines.extractors[self.settings.engine]()
            # Create a new model for the translation tab, bound to the file and engine
            model = TranslationTableModel(filters=self.filter_manager, file_path=file_path, engine=extractor)
            tab = self.translation_table.add_translation_tab(file_path.as_posix(), model=model)
            
            # Load units from the file using the bound engine
            model.load_from_file()
        
            self.settings.add_recent_file(file_path)  # Add the loaded file to recent
            # --- Auto-load dictionary ---
            dict_path = Path(self.settings.user_dict_dir)/f"{file_path.stem}.csv"
            if dict_path.exists():
                self.translation_table.apply_dictionary(dict_path, target_tab=file_path.as_posix())
            # ---------------------------

        except Exception as e:
            logger.exception(f"Failed to load game file {file_path}: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load game file:\n{e}")
            
    def save_game_file_dialog(self):
        if (model := self.translation_table.currentModel()) is None:
            logger.warning("No active translation tab to save.")
            return
        current_file = model.file_path
        default_name = current_file.name if current_file else "translated_file.json"
        save_path, _ = QFileDialog.getSaveFileName(self, L["file_dialog.save_translated_file"], default_name, "JSON Files (*.json);;All Files (*.*)")
        if not save_path:
            return  # User cancelled the save dialog
        try:
            model.save_to_game_file(save_path=save_path)
            self.statusBar().showMessage(L["statusBar.saved_success"], 3000)
            # TODO: Implement the status bar
        except Exception as e:
            logger.exception(f"Failed to save game file: {e}")
            QMessageBox.critical(self, "Save Error", f"Could not save game file:\n{e}")
    
    def save_game_file(self):        
        if (model := self.translation_table.currentModel()) is None:
            logger.warning("No active translation tab to save.")
            return
        try:
            model.save_to_game_file()
            # TODO: Implement the status bar
            self.statusBar().showMessage(L["statusBar.saved_success"], 3000)
        except Exception as e:
            logger.exception(f"Failed to save game file: {e}")
            QMessageBox.critical(self, "Save Error", f"Could not save game file:\n{e}")
        
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

