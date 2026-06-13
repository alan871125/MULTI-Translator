import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog, QMainWindow, QTabWidget, QWidget, 
    QVBoxLayout, QHBoxLayout, 
    QPushButton, QMessageBox,
    QInputDialog, QDialog, QDialogButtonBox,
    QMenu, QApplication, QShortcut, QComboBox, QAction,
)

from app.gui.theme import ThemeManager
from app.translation_table import TranslationTableModel, TranslationTableView, TranslationTabWidget
from app.language import LanguagePack
from app.settings import Settings, SettingsDialog
from .menu import initialize_menu
from .search import SearchDialog
import engines

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
L = LanguagePack()

@dataclass
class TableFilters:
    file: str = ""
    attribute: str = ""
    original: str = ""
    translated: str = ""
    
# Actors.json: name, nickname, profile
class TranslationApp(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        L.set_language(self.settings.language)
        ThemeManager().set_theme(dark = settings.dark_mode) # Apply theme based on settings at startup
        self.setWindowTitle("RPG Translator")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)
        self.initUI()
        self.init_hotkeys()
        if settings.restore_last_session:
            self.restore_open_tabs()  # Attempt to restore previously open tabs if the setting is enabled
        
    def closeEvent(self, event):
        # save the current state of the application
        open_tabs = self.translation_table.tabs.keys()
        self.settings.last_open_tabs = open_tabs  # Save the list of currently open tabs to
        self.settings.save()  # Save settings to persist the list of open tabs for the next session
        super().closeEvent(event)
    
    def restore_open_tabs(self):
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
        dialog = SearchDialog(self, filters=model.filters)
        dialog.replace_signal.connect(model.search_and_replace)  # Connect the replace signal to the model's replace method
        dialog.replace_widget.setVisible(False)  # Hide the replace button since we're only using this for filtering
        dialog.exec_()
        filters = dialog.get_filters()
        # Apply the filters to the table model
        model.set_filters(filters)
        
    def initUI(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.widgets = {}  # Dictionary to hold references to dynamically created widgets for easy access
        top_layout, top_widgets = self.init_top_bar()
        self.widgets.update(top_widgets)  # Store references to top bar widgets for later use
        self.translation_table = TranslationTabWidget()
        self.translation_table.setTabsClosable(True)
        self.translation_table.tabCloseRequested.connect(self.translation_table.removeTab)
        self.init_menu_bar() # Initialize the menu bar after creating the table and model, so that menu actions can interact with them
        self.main_layout.addLayout(top_layout)
        self.main_layout.addWidget(self.translation_table)
        
        # self.debug()  # Load test data # Remove this line in production #TODO
        
    def init_menu_bar(self):
        menu_def = {
            "file.load_game_file": self.load_game_file_dialog,
            "file.load_workspace": self.load_workspace_dialog,
            "file.new_workspace": self.load_workspace_dialog,
            "file.save_translation": self.translation_table.save_current_tab,
            "file.recent_files": QMenu,  # Placeholder for recent files submenu
            "file.save_game_file": self.save_game_file,
            "file.save_game_file_as": self.save_game_file_dialog,
            "settings": self.open_settings,
            "edit.undo": None,  # Placeholder for undo action
            "edit.redo": None,  # Placeholder for redo action
            "tools.chinese_conversion.chs2cht": self.translation_table.chs2cht_current_tab,
            "tools.chinese_conversion.cht2chs": self.translation_table.cht2chs_current_tab,  # Placeholder for Chinese conversion tool
        } 
        # use `$n:` as a special prefix before file paths in the menu definition 
        # to indicate that the menu item should use the file path as its name.
        
        menus = initialize_menu(self, menu_def, tr=L.__getitem__)
        menus["file.save_translation"].setEnabled(False)  # Disable save translation action until a tab is loaded with a file
        self.translation_table.tab_exist_signal.connect(lambda exist: menus["file.save_translation"].setEnabled(exist))  # Enable save action only when a tab with a loaded file exists
        self.lru_menu = menus.get("file.recent_files")
        self.refresh_recent_files_menu()  # Populate the recent files menu with the current list of recent files from settings
    
    def init_top_bar(self):
        layout = QHBoxLayout()
        widgets = {}
        current_workspace = Path(self.settings.workspace.workspace_dir or "Default").name
        widgets['top.filter_button'] = QPushButton("Filter", self)
        widgets['top.filter_button'].clicked.connect(self.open_filter_menu)
        widgets['top.workspace_button'] = QPushButton(current_workspace, self)
        widgets['top.workspace_button'].clicked.connect(self.load_workspace_dialog)
        widgets['top.engine_select'] = QComboBox()
        widgets['top.engine_select'].addItems(engines.supported_engines)
        widgets['top.engine_select'].setCurrentText(self.settings.engine)
        widgets['top.engine_select'].currentTextChanged.connect(self.on_engine_changed)
        
        for widget in widgets.values():
            layout.addWidget(widget)
        return layout, widgets
    
    def init_bottom_tab(self):
        """Includes the Dictionary and Fuzzy-matching suggestions for the current selected cell.
        """
        tab_widget = QTabWidget()
        tab_widget.addTab(QWidget(), L["bottom_tab.dictionary"])
        tab_widget.addTab(QWidget(), L["bottom_tab.fuzzy_suggestions"])
        return tab_widget
    
    def refresh_recent_files_menu(self):
        assert isinstance(self.lru_menu, QMenu), "Recent Files menu should be a QMenu instance."
        self.lru_menu.clear()
        lru_iter = self.settings._recent_files.iter(reverse=True)  # Show most recent files at the top
        dir_def = {}# workspaces
        file_def = {}  # individual files
        for path in lru_iter:
            if path.is_dir() or path.suffix == ".translation-workspace":
                dir_def['$n:'+path.as_posix()] = lambda check,fp=path: self.load_workspace(fp)
            else:
                file_def['$n:'+path.as_posix()]= lambda check,fp=path: self.load_game_file(fp)
        # file_def = {f"{i}$n:{fp.as_posix()}": lambda check,fp=fp: self.load_game_file(fp) for i,fp in enumerate(lru_iter)}
        recent_files_def = dir_def | {'$n:separator1':'$separator'}|file_def  # Merge directory and file definitions, directories will be listed before files
        lru_menus = initialize_menu(self, menu_def = recent_files_def, root_menu=self.lru_menu, root_menu_name="file.recentFiles", tr=lambda x:x)  # Initialize an empty submenu for recent files

    def init_hotkeys(self):
        self.hotkeys = {
            "save": QShortcut(Qt.CTRL + Qt.Key_S, self),
            "search": QShortcut(Qt.CTRL + Qt.Key_F, self),
        }
        self.hotkeys["save"].activated.connect(self.translation_table.save_current_tab)
        self.hotkeys["save"].setEnabled(False)  # Disable save hotkey until a tab with a loaded file exists
        self.hotkeys["search"].activated.connect(self.open_filter_menu)
        self.translation_table.tab_exist_signal.connect(lambda exist:self.hotkeys["save"].setEnabled(exist))  # Enable save action only when a tab with a loaded file exists

    def load_translations(self): 
        pass #TODO: implement loading translation dictionary from previous sessions to avoid losing work and to reuse translations across similar text in different files
    
    def load_workspace_dialog(self):
        workspace_dir = QFileDialog.getExistingDirectory(self, L["FileDialoge.select_workspace_dir"], "")
        if workspace_dir:
            self.load_workspace(workspace_dir)
            
    
    def load_workspace(self, config_path: str|Path):
        config_path = Path(config_path).absolute()
        self.settings.workspace.load_update(config_path)
        self.settings._recent_files.add_recent_file(config_path)  # Add the loaded workspace to recent files
        self.settings.save()  # Save settings to persist the updated recent files list
        self.refresh_recent_files_menu()  # Refresh the recent files menu to reflect the updated list
        self.widgets['top.workspace_button'].setText(Path(config_path).stem)  # Update the workspace button text to show the name of the loaded workspace
        
    def load_game_file_dialog(self):
        # import supported file types from the selected engine
        extractor = engines.extractors[self.settings.engine]()
        supported_types = extractor.SUPPORTED_FILES_TYPES
        file_filters = ";;".join(f"{ft.upper()} Files (*{ft})" for ft in supported_types)+f";;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(self, L["file_dialog.select_game_file"], "", file_filters)
        if not file_path:
            return  # User cancelled the file dialog
        self.load_game_file(file_path)
        
    def load_game_file(self, file_path: str|Path):
        file_path = Path(file_path).absolute()  # Normalize the file path
        try:
            extractor = engines.extractors[self.settings.engine]()
            # Create a new model for the translation tab, bound to the file and engine
            model = TranslationTableModel(file_path=file_path, engine=extractor) 
            tab = self.translation_table.add_translation_tab(file_path.as_posix(), model=model)
            
            # Load units from the file using the bound engine
            model.load_from_file()
        
            self.settings._recent_files.add_recent_file(file_path)  # Add the loaded file to recent
            self.settings.save()  # Save settings to persist the updated recent files list
            self.refresh_recent_files_menu()  # Refresh the recent files menu to reflect the updated list
            
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
            model.save_to_game_file(save_path=save_path)  # Save the current tab's translations back to a game file using the bound engine's apply_translations method
            self.statusBar().showMessage(L["statusBar.saved_success"], 3000)  # Optional: show a success message in status bar
        except Exception as e:
            logger.exception(f"Failed to save game file: {e}")
            QMessageBox.critical(self, "Save Error", f"Could not save game file:\n{e}")
    
    def save_game_file(self):        
        if (model := self.translation_table.currentModel()) is None:
            logger.warning("No active translation tab to save.")
            return
            
        try:
            model.save_to_game_file()
            # Optional: show a success message in status bar
            self.statusBar().showMessage(L["statusBar.saved_success"], 3000)
        except Exception as e:
            logger.exception(f"Failed to save game file: {e}")
            QMessageBox.critical(self, "Save Error", f"Could not save game file:\n{e}")
        
        
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_()== QDialog.Accepted:
            dialog.save_settings()
            L.set_language(self.settings.language) #TODO: optimize by only reloading translations if language actually changed
            # TODO: update UI language immediately without needing to restart the app. This requires all UI text to be retrieved from LanguagePack with the current language, and emitting signals to update text when language changes.
            logger.debug("Settings saved")
            # Persist and apply theme immediately
            try:
                self.settings.save()
            except Exception:
                logger.exception("Failed to save settings.json")
            ThemeManager().set_theme(dark = self.settings.dark_mode)
        else:
            logger.debug("Settings dialog cancelled")

    def on_engine_changed(self, engine_name:str):
        self.settings.engine = engine_name
        self.settings.save()  # Save settings immediately when engine is changed to persist the choice
        logger.debug(f"Engine changed to {engine_name}, settings saved.")
