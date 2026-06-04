import json
import logging
import PyQt5.QtWidgets as qt
from typing import cast
from pathlib import Path
from dataclasses import dataclass, asdict, field
from app.gui.theme import ThemeManager
from app.translation_table import TranslationTableModel
from deep_translator import GoogleTranslator

from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDropEvent, QCursor, QIcon
from PyQt5.QtWidgets import QTableWidget, QDialogButtonBox

from app.language import LanguagePack
from app.settings import Settings, SettingsDialog
from .search import SearchDialog
import engines

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
L = LanguagePack()

def translate(source, source_lang="auto", target_lang="en"):
    if not source or not source.strip():
        return
    # Call translation API (e.g. Google Translate) and update translation
    try:
        translated = GoogleTranslator(source_lang, target_lang).translate(source)
    except Exception as e:
        logger.error(f"Translation API error: {e}")
    return translated

@dataclass
class TableFilters:
    file: str = ""
    attribute: str = ""
    original: str = ""
    translated: str = ""
    
class TranslationTableView(qt.QTableView):
    # TODO: AI GENERATED: NEED REVIEW
    def __init__(self, parent=None):
        super().__init__(parent)
        # Use row selection and single selection so a row is selected at a time
        self.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        # self.setAlternatingRowColors(True)
        # enable custom context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # allow inline editing via double-click or edit key
        self.setEditTriggers(qt.QAbstractItemView.DoubleClicked | qt.QAbstractItemView.EditKeyPressed | qt.QAbstractItemView.SelectedClicked)

    def edit_translation_row(self, row: int, model: TranslationTableModel) -> None:
        current = model.data(model.index(row, model._columns.index("translation")), Qt.DisplayRole)
        text, ok = qt.QInputDialog.getText(self, "Edit Translation", "Translation:", text=str(current))
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
        menu = qt.QMenu(self)
        
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
                if original is not None and (translated:=translate(original)) is not None:
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
            qt.QApplication.clipboard().setText(str(original))

    
# Actors.json: name, nickname, profile
class TranslationApp(qt.QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        ThemeManager().set_theme(dark = settings.dark_mode) # Apply theme based on settings at startup
        self.setWindowTitle("RPG Translator")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)
        self.initUI()
        self.init_hotkeys()
        L.set_language(self.settings.language)
    
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
        self.init_menu_bar()
        self.central_widget = qt.QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = qt.QVBoxLayout(self.central_widget)
        
        functions_layout = qt.QHBoxLayout()
        widgets = {}
        widgets['engine_select'] = qt.QComboBox()
        widgets['engine_select'].addItems(engines.supported_engines)
        widgets['filter_button'] = qt.QPushButton("Filter", self)
        widgets['filter_button'].clicked.connect(self.open_filter_menu)
        functions_layout.addWidget(widgets['filter_button'])
        functions_layout.addWidget(widgets['engine_select'])
        
        self.table = TranslationTableView(self)
        self.model = TranslationTableModel([])
        self.debug()  # Load test data # Remove this line in production #TODO
        self.table.setModel(self.model)
        
        self.main_layout.addLayout(functions_layout)
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
        
    def init_hotkeys(self):
        self.hotkeys = {
            "save": qt.QShortcut(Qt.CTRL + Qt.Key_S, self),
            "search": qt.QShortcut(Qt.CTRL + Qt.Key_F, self),
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
        with open("test/dictionary.json", "r", encoding="utf-8") as f:
            self.model.translated_mapping = json.load(f)
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
            ThemeManager().set_theme(dark = self.settings.dark_mode)
        else:
            logger.debug("Settings dialog cancelled")