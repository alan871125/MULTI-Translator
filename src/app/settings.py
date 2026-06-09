import os
import json
import logging  
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Any
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QVBoxLayout, QFormLayout, QGroupBox, QHBoxLayout,
    QCheckBox, QSpinBox, QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, QTabWidget, QWidget
)
import inspect
from core.translation.providers._base import Language
from utils import JSONWithCommentsDecoder
from lru_file import LeastRecentlyUsedFiles
# from engines import supported_engines
from .language import LanguagePack
from core.translation.providers import providers

logger = logging.getLogger(__name__)
L = LanguagePack()


@dataclass
class Settings:
    # Engine
    engine: str = "RPG Maker MV"
    
    data_dir: str = "./data"
    
    # Translation
    SOURCE_LANG: str = "auto" # should be saved as language code, but can be displayed as language name in the UI
    TARGET_LANG: str = "en"   # should be saved as language code, but can be displayed as language name in the UI
    API: str = "google"
    DEEPL_API_KEY: str = ""
    CUSTOM_API_KEY: str = ""
    CUSTOM_API_URL: str = "https://openrouter.ai/api/v1/chat/completions" # This is used for custom API, ignored for built-in APIs like Google Translate
    max_workers: int = 4
    
    # Theme and UI
    language: str = "en"
    dark_mode: bool = False
    theme: str = "default"
    
    _recent_files: LeastRecentlyUsedFiles = field(init = False, default_factory=LeastRecentlyUsedFiles)

    def __getitem__(self, key):
        return getattr(self, key)
    
    def __setitem__(self, key, value):
        setattr(self, key, value)
    
    def get(self, key:str, default:Any=None):
        return getattr(self, key, default)
    
    def asdict(self) -> dict:
        d = asdict(self)
        d["_recent_files"] = self._recent_files.to_list()
        return d
    
    @classmethod
    def from_dict(cls,data: dict) -> "Settings":
        valid_fields = inspect.signature(cls).parameters
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        settings = Settings(**filtered_data)
        settings._recent_files = LeastRecentlyUsedFiles.from_list(data.get("_recent_files", []))
        return settings
    
    @staticmethod    
    def load(path: str|Path):
        try:
            with open(path, "r") as f:
                data = json.load(f, cls=JSONWithCommentsDecoder)
            settings = Settings.from_dict(data)
        except FileNotFoundError:
            logger.info("Initializing new settings with default values.")
            settings=Settings()  # Return default settings if file not found
        except Exception as e:
            logger.error(f"Failed to load settings from {path}: {e}")
            settings=Settings()  # Return default settings on failure
        settings.DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", settings.DEEPL_API_KEY)
        settings.CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", settings.CUSTOM_API_KEY)
        return settings
    
    def save(self, path: str|Path="settings.json"):
        settings = self.asdict()
        DEEPL_API_KEY =settings.pop("DEEPL_API_KEY", "")
        CUSTOM_API_KEY = settings.pop("CUSTOM_API_KEY", "")
        if DEEPL_API_KEY or CUSTOM_API_KEY:  # Remove CUSTOM_API_KEY from the settings to be save in .env file
            import dotenv
            dotenv.set_key(".env", "DEEPL_API_KEY", DEEPL_API_KEY)
            dotenv.set_key(".env", "CUSTOM_API_KEY", CUSTOM_API_KEY)
        try:
            with open(path, "w") as f:
                json.dump(settings,  f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save settings to {path}: {e}")
            
class PathSettingsLayout(QHBoxLayout):
    def __init__(self, default_path:str|Path, browse_type: str = "dir"):
        super().__init__()
        self.path_edit = QLineEdit()
        self.path_edit.setText(str(default_path))
        self.path_edit.setReadOnly(False)
        self.addWidget(self.path_edit)
        self.browse_button = QPushButton(L["browse"])
        self.browse_button.clicked.connect(self.browse_path)
        self.addWidget(self.browse_button)
        self.browse_type = browse_type
        
    def text(self) -> str:
        return self.path_edit.text().strip()
    
    def browse_path(self):
        current_path = self.path_edit.text().strip()
        options = "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(
            None, "Select File", current_path,
            options
        )
        if path:
            self.path_edit.setText(path)
    
class SettingsDialog(QDialog):
    """Settings dialog window"""
    DEFAULT_LANGUAGES = [
        Language(code="en",    name="English"),
        Language(code="zh-TW", name="Chinese (Traditional)"),
        Language(code="zh-CN", name="Chinese (Simplified)"),
        Language(code="jp",    name="Japanese"),
        Language(code="ko",    name="Korean"),
        Language(code="fr",    name="French"),
        Language(code="de",    name="German"),
        Language(code="ru",    name="Russian")
    ]
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings: Settings = settings
        self.setWindowTitle(L["Settings"])
        self.setMinimumSize(700, 270)        
        self.init_ui()

    def update_lang_combobox(self, combo_box: QComboBox, current_lang:str, role:str, has_auto:bool=True):
        # prevent updating before the combo boxes are initialized
        api = self.widgets["translator"]["API"].currentText()
        supported_langs: list[Language] = [Language(code="auto", name="Auto")] if has_auto else []
        if api in providers:
            provider = providers[api]
            if role == 'source':
                supported_langs.extend(provider.SOURCE_SUPPORTED_LANGUAGES.values())
            elif role == 'target':
                supported_langs.extend(provider.TARGET_SUPPORTED_LANGUAGES.values())
            else:
                raise ValueError(f"Invalid role: {role}. Must be 'source' or 'target'.")
        else:
            supported_langs.extend(self.DEFAULT_LANGUAGES)
        combo_box.clear()
        for i,lang in enumerate(supported_langs):
            combo_box.addItem(lang, lang.code)
            if lang.code == current_lang:
                combo_box.setCurrentIndex(i)
    
    def on_api_changed(self, api_name:str):
        self.update_lang_combobox(self.widgets["translator"]["SOURCE_LANG"], self.settings.SOURCE_LANG, role='source')
        self.update_lang_combobox(self.widgets["translator"]["TARGET_LANG"], self.settings.TARGET_LANG, role='target', has_auto=False)

    def init_ui(self):
        """Initialize the settings UI"""
        self.settings_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.settings_layout.addWidget(self.tabs)
        self.widgets = {"translator": {}, "UI": {}, "dictionary": {}}
        self.layouts = {}        
        self.init_translator_settings_tab()
        self.init_ui_settings_tab()
        self.init_dictionary_settings_tab()
        
        self.settings_layout.addStretch()
        # Dialog buttons (OK/Cancel)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.settings_layout.addWidget(button_box)
        
    def init_dictionary_settings_tab(self):
        dictionary_tab = QWidget()
        self.layouts["dictionary"] = QFormLayout(dictionary_tab)
        self.widgets["dictionary"]["dataDir"] = PathSettingsLayout(self.settings.data_dir, browse_type="dir")
        self.layouts["dictionary"].addRow(L["settings.dictionary.dataDir"], self.widgets["dictionary"]["dataDir"])
        self.tabs.addTab(dictionary_tab, L["Dictionary"])
        
    def init_translator_settings_tab(self):
        # Translation Settings Tab
        translation_tab = QWidget()
        ## dropdown Menus
        self.layouts["translator"] = QFormLayout(translation_tab)
        self.widgets["translator"]["SOURCE_LANG"] = QComboBox()
        self.widgets["translator"]["TARGET_LANG"] = QComboBox()
        self.widgets["translator"]["API"] = QComboBox()
        self.widgets["translator"]["API"].addItems([L[p] for p in providers.keys()])
        self.widgets["translator"]["API"].setCurrentText(self.settings.API)
        self.widgets["translator"]["API"].currentTextChanged.connect(self.on_api_changed)
        # Update language combo boxes based on the current API setting
        self.update_lang_combobox(self.widgets["translator"]["SOURCE_LANG"], self.settings.SOURCE_LANG, role='source')
        self.update_lang_combobox(self.widgets["translator"]["TARGET_LANG"], self.settings.TARGET_LANG, role='target', has_auto=False)
        
        ## Line Edits
        self.widgets["translator"]["DEEPL_API_KEY"] = QLineEdit(self.settings.DEEPL_API_KEY)
        self.widgets["translator"]["CUSTOM_API_KEY"] = QLineEdit(self.settings.CUSTOM_API_KEY)
        self.widgets["translator"]["CUSTOM_API_URL"] = QLineEdit(self.settings.CUSTOM_API_URL)
        self.widgets["translator"]["DEEPL_API_KEY"].setPlaceholderText(L["DEEPL_API_KEY.hint"])
        self.widgets["translator"]["CUSTOM_API_KEY"].setPlaceholderText(L["CUSTOM_API_KEY.hint"])
        self.tabs.addTab(translation_tab, L["translator"])
        
    def init_ui_settings_tab(self):        
        languages = L.get_available_languages()
        # UI Settings Tab
        ui_tab = QWidget()
        self.layouts["UI"] = QFormLayout(ui_tab)
        self.widgets["UI"]["language"] = QComboBox()
        self.widgets["UI"]["language"].addItems(languages)
        self.widgets["UI"]["language"].setCurrentText(self.settings.language)
        self.widgets["UI"]["fontSize"] = QSpinBox()
        self.widgets["UI"]["fontSize"].setRange(8, 24)
        self.widgets["UI"]["fontSize"].setValue(14)
        self.widgets["UI"]["dark_mode"] = QCheckBox()
        self.widgets["UI"]["dark_mode"].setChecked(self.settings.dark_mode)
        self.tabs.addTab(ui_tab, L["UI"])
        for layout_key, form_layout in self.layouts.items():
            for k, widget in self.widgets[layout_key].items():
                form_layout.addRow(L[k], widget)
        
    def save_settings(self):
        """Update settings from the dialog inputs"""
        for widgets in self.widgets.values():
            for k, widget in widgets.items():
                if k in ["SOURCE_LANG", "TARGET_LANG"]:
                    self.settings[k] = widget.currentData()  # Get the language code from the combo box
                elif isinstance(widget, QComboBox):
                    self.settings[k] = widget.currentText()
                elif isinstance(widget, QLineEdit):
                    self.settings[k] = widget.text().strip()
                elif isinstance(widget, QCheckBox):
                    self.settings[k] = widget.isChecked()