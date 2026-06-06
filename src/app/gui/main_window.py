import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, 
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
        widgets['filter_button'] = QPushButton("Filter", self)
        widgets['filter_button'].clicked.connect(self.open_filter_menu)
        functions_layout.addWidget(widgets['filter_button'])
        functions_layout.addWidget(widgets['engine_select'])
        
        self.table = TranslationTableView(self)
        self.model = TranslationTableModel([])
        self.debug()  # Load test data # Remove this line in production #TODO
        self.table.setModel(self.model)
        
        self.init_menu_bar() # Initialize the menu bar after creating the table and model, so that menu actions can interact with them
        self.main_layout.addLayout(functions_layout)
        self.main_layout.addWidget(self.table)
        
        for col, width in enumerate(TranslationTableModel._COLWIDTHS):
            self.table.setColumnWidth(col, width)
        # make header stretch for readability
        self.table.horizontalHeader().setStretchLastSection(False)
    

        
    
    def init_menu_bar(self):
        menu_def = {
            "file.saveTranslation": self.save_translations,
            "file.loadGameFile": self.load_game_file,
            "file.saveGameFile": self.save_game_file,
            "settings": self.open_settings,
            "edit.undo": None,  # Placeholder for undo action
            "edit.redo": None,  # Placeholder for redo action
            "tools.chineseConversion.chs2cht": self.model.chs2cht,  # Placeholder for Chinese conversion tool
            "tools.chineseConversion.cht2chs": self.model.cht2chs,  # Placeholder for Chinese conversion tool
        }
        menus = initialize_menu(self, menu_def, tr=L.__getitem__)
        
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
    def load_game_file(self):        pass #TODO: implement loading a game data file (e.g. Actors.json) and extracting translatable text to add to the table for translation
    def save_game_file(self):        pass #TODO: implement saving the game data file with
    
    
    def debug(self):
        # with open("test/dictionary.json", "r", encoding="utf-8") as f:
        #     self.model.translated_mapping = json.load(f)
        # from engines.rpgmaker_mv.extractor import RPGMakerMVExtractor
        extractor = engines.extractors[self.settings.engine]()
        # self.model.load_units(extractor.extract_file("test/Actors.json"))
        # self.model.load_units(extractor.extract_file("test/Armors.json"))
        # self.model.load_units(extractor.extract_file("test/Items.json"))
        # self.model.load_units(extractor.extract_file("test/Classes.json"))
        # self.model.load_units(extractor.extract_file("test/CommonEvents.json"))
        self.model.load_units(extractor.extract_file("test/Map001.json"))
        
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