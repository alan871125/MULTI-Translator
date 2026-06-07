import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog, QMainWindow, QWidget, 
    QVBoxLayout, QHBoxLayout, 
    QPushButton, 
    QInputDialog, QDialog, QDialogButtonBox,
    QMenu, QApplication, QShortcut, QComboBox, QAction,
)

from app.gui.theme import ThemeManager
from app.translation_table import TranslationTableModel, TranslationTableView
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
    
    def open_filter_menu(self):
        # Popup a filter Menu with Column: entries for columns in the table.
        dialog = SearchDialog(self, filters=self.model.filters)
        dialog.replace_signal.connect(self.model.search_and_replace)  # Connect the replace signal to the model's replace method
        dialog.replace_widget.setVisible(False)  # Hide the replace button since we're only using this for filtering
        dialog.exec_()
        filters = dialog.get_filters()
        # Apply the filters to the table model
        self.model.set_filters(filters)
        
    def initUI(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        functions_layout = QHBoxLayout()
        widgets = {}
        widgets['engine_select'] = QComboBox()
        widgets['engine_select'].addItems(engines.supported_engines)
        widgets['engine_select'].setCurrentText(self.settings.engine)
        widgets['engine_select'].currentTextChanged.connect(self.on_engine_changed)
        widgets['filter_button'] = QPushButton("Filter", self)
        widgets['filter_button'].clicked.connect(self.open_filter_menu)
        functions_layout.addWidget(widgets['filter_button'])
        functions_layout.addWidget(widgets['engine_select'])
        
        self.table = TranslationTableView(self)
        self.model = TranslationTableModel([])
        self.table.setModel(self.model)
        
        self.init_menu_bar() # Initialize the menu bar after creating the table and model, so that menu actions can interact with them
        self.main_layout.addLayout(functions_layout)
        self.main_layout.addWidget(self.table)
        
        for col, width in enumerate(TranslationTableModel._COLWIDTHS):
            self.table.setColumnWidth(col, width)
        # make header stretch for readability
        self.table.horizontalHeader().setStretchLastSection(False)
        self.debug()  # Load test data # Remove this line in production #TODO
        
    def on_engine_changed(self, engine_name:str):
        self.settings.engine = engine_name
        self.settings.save()  # Save settings immediately when engine is changed to persist the choice
        logger.debug(f"Engine changed to {engine_name}, settings saved.")
        
    def init_menu_bar(self):
        menu_def = {
            "file.saveTranslation": self.save_translations,
            "file.loadGameFile": self.load_game_file_dialog,
            "file.saveGameFile": self.save_game_file,
            "file.recentFiles": QMenu,  # Placeholder for recent files submenu
            "settings": self.open_settings,
            "edit.undo": None,  # Placeholder for undo action
            "edit.redo": None,  # Placeholder for redo action
            "tools.chineseConversion.chs2cht": self.model.chs2cht,  # Placeholder for Chinese conversion tool
            "tools.chineseConversion.cht2chs": self.model.cht2chs,  # Placeholder for Chinese conversion tool
        } 
        # use `$n:` as a special prefix before file paths in the menu definition 
        # to indicate that the menu item should use the file path as its name.
        
        menus = initialize_menu(self, menu_def, tr=L.__getitem__)
        self.lru_menu = menus.get("file.recentFiles")
        self.refresh_recent_files_menu()  # Populate the recent files menu with the current list of recent files from settings
            # # Dynamicallymenus add recent files to the File menu
        # if (lru_menu:=.get("file.recentFiles")) and isinstance(lru_menu, QMenu):
        #     for file_path in self.settings._recent_files.iter(reverse=True):  # Show most recent files at the top
        #         action = QAction(file_path.as_posix(), self)
        #         action.triggered.connect(lambda checked, fp=file_path: self.load_game_file(fp))
        #         lru_menu.addAction(action)
        
    def refresh_recent_files_menu(self):
        assert isinstance(self.lru_menu, QMenu), "Recent Files menu should be a QMenu instance."
        self.lru_menu.clear()
        lru_iter = self.settings._recent_files.iter(reverse=True)  # Show most recent files at the top
        file_def = {f"{i}$n:{fp.as_posix()}": lambda : self.load_game_file(fp) for i,fp in enumerate(lru_iter)}
        lru_menus = initialize_menu(self, menu_def = file_def, root_menu=self.lru_menu, root_menu_name="file.recentFiles", tr=lambda x:x)  # Initialize an empty submenu for recent files

    def init_hotkeys(self):
        self.hotkeys = {
            "save": QShortcut(Qt.CTRL + Qt.Key_S, self),
            "search": QShortcut(Qt.CTRL + Qt.Key_F, self),
        }
        self.hotkeys["save"].activated.connect(self.save_translations)
        self.hotkeys["search"].activated.connect(self.open_filter_menu)

    def save_translations(self):
        pass #TODO: implement saving translation dictionary to reuse for later sessions
    def load_translations(self): 
        pass #TODO: implement loading translation dictionary from previous sessions to avoid losing work and to reuse translations across similar text in different files
    
    def load_game_file_dialog(self):
        # import supported file types from the selected engine
        extractor = engines.extractors[self.settings.engine]()
        supported_types = extractor.SUPPORTED_FILES_TYPES
        file_filters = ";;".join(f"{ft.upper()} Files (*{ft})" for ft in supported_types)+f";;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(self, L["fileDialoge.SelectGameFile"], "", file_filters)
        if not file_path:
            return  # User cancelled the file dialog
        self.load_game_file(file_path)
    def load_game_file(self, file_path: str|Path):
        file_path = Path(file_path).absolute()  # Normalize the file path
        extractor = engines.extractors[self.settings.engine]()        
        self.model.load_units(extractor.extract_file(file_path))
        self.settings._recent_files.add_recent_file(file_path)  # Add the loaded file to recent
        self.settings.save()  # Save settings to persist the updated recent files list
        self.refresh_recent_files_menu()  # Refresh the recent files menu to reflect the updated list

    def save_game_file(self):        pass #TODO: implement saving the game data file with
    
    
    def debug(self):
        self.settings.engine = "RPG Maker MV"
        self.settings.save()  # Save settings immediately when engine is changed to persist the choice
        self.load_game_file("test/data/Actors.json")
        pass
        # with open("test/dictionary.json", "r", encoding="utf-8") as f:
        #     self.model.translated_mapping = json.load(f)
        # from engines.rpgmaker_mv.extractor import RPGMakerMVExtractor
        # extractor = engines.extractors[self.settings.engine]()
        # self.model.load_units(extractor.extract_file("test/Actors.json"))
        # self.model.load_units(extractor.extract_file("test/Armors.json"))
        # self.model.load_units(extractor.extract_file("test/Items.json"))
        # self.model.load_units(extractor.extract_file("test/Classes.json"))
        # self.model.load_units(extractor.extract_file("test/CommonEvents.json"))
        # self.model.load_units(extractor.extract_file("test/Map001.json"))
        
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
