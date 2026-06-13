import os
import json
import logging  
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Any, Optional
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QVBoxLayout, QFormLayout, QGroupBox, QHBoxLayout,
    QCheckBox, QSpinBox, QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, QTabWidget, QWidget
)
import inspect
from core.translation import Language, providers, get_supported_languages
from utils import JSONWithCommentsDecoder
from lru_file import LeastRecentlyUsedFiles
# from engines import supported_engines
from .language import LanguagePack

logger = logging.getLogger(__name__)
L = LanguagePack()

@dataclass
class WorkspaceSettings:
    """Settings specific to the translation workspace, including paths and last opened tabs."""
    workspace_dir: Optional[str] = None  # None means the global default workspace
    game_data_dir: Optional[str] = None
    user_dict_dir: Optional[str] = None
    output_dir: str = "./output"
    engine: str = "RPG Maker MV"
    last_open_tabs: list[str] = field(default_factory=list)
    
    def asdict(self) -> dict:
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})
    
    @classmethod
    def load(cls, path: str|Path="./workspace.translation-workspace") -> 'WorkspaceSettings':
        path = Path(path)
        if path.is_dir():
            if (path / "workspace.translation-workspace").exists():
                path = path / "workspace.translation-workspace"
            else: 
                logging.info(f"No workspace settings file found in {path}. Initializing with default settings.")
                return cls(workspace_dir=path.as_posix())
        if path.suffix!=".translation-workspace":
            logger.warning(f"Loading workspace settings from a file with unexpected extension: {path}. Expecting '.translation-workspace' but loading anyway.")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)
        
    def load_update(self, path: str|Path="./workspace.translation-workspace"):
        """Load workspace settings from a file and update the current settings. This is useful for loading a workspace without affecting the global settings."""
        new_settings = self.load(path)
        for field_name in asdict(self).keys():
            new_value = getattr(new_settings, field_name)
            if new_value is not None:
                setattr(self, field_name, new_value)
                
    def save(self, path: Optional[str|Path] = None):
        workspace_dir = self.workspace_dir or "."
        if path is None:
            path = Path(workspace_dir) / "workspace.translation-workspace"
        else:
            path = Path(path)
        if path.suffix != ".translation-workspace":
            logger.warning(f"Saving workspace settings to a file with unexpected extension: {path}. Expecting '.translation-workspace'.")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.asdict(), f, indent=4, ensure_ascii=False)

@dataclass
class Settings:    
    # Translation
    SOURCE_LANG: str = "auto" # should be saved as language code, but can be displayed as language name in the UI
    TARGET_LANG: str = "en"   # should be saved as language code, but can be displayed as language name in the UI
    API: str = "Google"
    DEEPL_API_KEY: str = ""
    CUSTOM_API_KEY: str = ""
    CUSTOM_API_URL: str = "https://openrouter.ai/api/v1" # This is used for custom API, ignored for built-in APIs like Google Translate
    CUSTOM_API_MODEL: str = "openrouter/free"
    max_workers: int = 4
    
    # Theme and UI
    language: str = "en"
    dark_mode: bool = False
    theme: str = "default"
    
    # Recent files and session
    restore_last_session: bool = True
    _recent_files: LeastRecentlyUsedFiles = field(init = False, default_factory=LeastRecentlyUsedFiles)

    workspace: WorkspaceSettings = field(init=False, default_factory=WorkspaceSettings)
    
    def __getitem__(self, key):
        return getattr(self, key)
    
    def __setitem__(self, key, value):
        setattr(self, key, value)
    
    @property
    def game_data_dir(self) -> str:
        return self.workspace.game_data_dir or "./data"
    @property
    def output_dir(self) -> str:
        return self.workspace.output_dir
    @property
    def user_dict_dir(self) -> str:
        return (Path(self.workspace.user_dict_dir or '.')/"dictionary").as_posix()
    @property
    def last_open_tabs(self) -> list[str]:
        return self.workspace.last_open_tabs
    @last_open_tabs.setter
    def last_open_tabs(self, tabs: list[str]):
        self.workspace.last_open_tabs = tabs
    @property
    def engine(self) -> str:
        return self.workspace.engine
    @engine.setter
    def engine(self, value: str):
        self.workspace.engine = value
    
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
        settings = cls(**filtered_data)
        settings._recent_files = LeastRecentlyUsedFiles.from_list(data.get("_recent_files", []))
        return settings
    
    @classmethod    
    def load(cls, path: str|Path, workspace_path: Optional[str|Path] = None) -> "Settings":
        try:
            with open(path, "r") as f:
                data = json.load(f, cls=JSONWithCommentsDecoder)
            settings = cls.from_dict(data)
        except FileNotFoundError:
            logger.info("Initializing new settings with default values.")
            settings=cls()  # Return default settings if file not found
        except Exception as e:
            logger.error(f"Failed to load settings from {path}: {e}")
            settings=cls()  # Return default settings on failure
        settings.DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", settings.DEEPL_API_KEY)
        settings.CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", settings.CUSTOM_API_KEY)
        if workspace_path and Path(workspace_path).exists():
            settings.workspace = WorkspaceSettings.load(workspace_path)
        else:
            settings.workspace = WorkspaceSettings(**data.get("workspace", {}))
        return settings
    
    def save(self, path: str|Path="settings.json"):
        settings = self.asdict()
        DEEPL_API_KEY =settings.pop("DEEPL_API_KEY", "")
        CUSTOM_API_KEY = settings.pop("CUSTOM_API_KEY", "")
        settings.pop("workspace", None)  # Workspace settings are saved separately in the workspace directory
        if self.workspace.workspace_dir is not None:
            self.workspace.save(path=None)  # Save workspace settings to its own file in the workspace directory
        else:
            self.workspace.save(path="./default.translation-workspace")  # Save workspace settings to a separate file with the same name but .translation-workspace extension
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
            if role == 'source':
                supported_langs.extend(get_supported_languages(self.settings.API, role='source'))
            elif role == 'target':
                supported_langs.extend(get_supported_languages(self.settings.API, role='target'))
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
        self.widgets = {"translator": {}, "UI": {}, "dictionary": {}, "startup": {}, "workspace": {}}
        self.layouts = {}        
        self.init_translator_settings_tab()
        self.init_ui_settings_tab()
        self.init_startup_settings_tab()
        self.init_workspace_settings_tab()
        
        for layout_key, form_layout in self.layouts.items():
            for k, widget in self.widgets[layout_key].items():
                form_layout.addRow(L[f"settings.{layout_key}.{k}"], widget)
                
        self.settings_layout.addStretch()
        # Dialog buttons (OK/Cancel)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.settings_layout.addWidget(button_box)
        
    def init_startup_settings_tab(self):
        startup_tab = QWidget()
        self.layouts["startup"] = QFormLayout(startup_tab)
        self.widgets["startup"]["restore_last_session"] = QCheckBox()
        self.widgets["startup"]["restore_last_session"].setChecked(self.settings.restore_last_session)
        # self.layouts["startup"].addRow(L["settings.startup.restoreLastSession"], self.widgets["startup"]["restoreLastSession"])
        self.tabs.addTab(startup_tab, L["Startup"])
        
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
        self.widgets["translator"]["CUSTOM_API_MODEL"] = QLineEdit(self.settings.CUSTOM_API_MODEL)
        self.widgets["translator"]["DEEPL_API_KEY"].setPlaceholderText(L["settings.translator.DEEPL_API_KEY.hint"])
        self.widgets["translator"]["CUSTOM_API_KEY"].setPlaceholderText(L["settings.translator.CUSTOM_API_KEY.hint"])
        self.tabs.addTab(translation_tab, L["settings.translator"])
        
    def init_ui_settings_tab(self):        
        languages = L.get_available_languages()
        # UI Settings Tab
        ui_tab = QWidget()
        self.layouts["UI"] = QFormLayout(ui_tab)
        self.widgets["UI"]["language"] = QComboBox()
        self.widgets["UI"]["language"].addItems(languages)
        self.widgets["UI"]["language"].setCurrentText(self.settings.language)
        self.widgets["UI"]["font_size"] = QSpinBox()
        self.widgets["UI"]["font_size"].setRange(8, 24)
        self.widgets["UI"]["font_size"].setValue(14)
        self.widgets["UI"]["dark_mode"] = QCheckBox()
        self.widgets["UI"]["dark_mode"].setChecked(self.settings.dark_mode)
        self.tabs.addTab(ui_tab, L["settings.UI"])
                
    def init_workspace_settings_tab(self):
        from engines import supported_engines
        workspace_tab = QWidget()
        self.layouts["workspace"] = QFormLayout(workspace_tab)
        self.widgets["workspace"]["workspace_dir"] = PathSettingsLayout(self.settings.workspace.workspace_dir or "./", browse_type="dir")
        self.widgets["workspace"]["game_data_dir"] = PathSettingsLayout(self.settings.game_data_dir, browse_type="dir")
        self.widgets["workspace"]["output_dir"] = PathSettingsLayout(self.settings.workspace.output_dir, browse_type="dir")
        self.widgets["workspace"]["engine"] = QComboBox()
        self.widgets["workspace"]["engine"].addItems(supported_engines)
        self.widgets["workspace"]["engine"].setCurrentText(self.settings.engine)
        self.widgets["workspace"]["engine"].setCurrentText(self.settings.workspace.engine)
        self.tabs.addTab(workspace_tab, L["settings.workspace"])
        
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