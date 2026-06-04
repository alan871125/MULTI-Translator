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
from utils import JSONWithCommentsDecoder
# from engines import supported_engines
from .language import LanguagePack

logger = logging.getLogger(__name__)
L = LanguagePack()


@dataclass
class Settings:
    # Engine
    engine: str = "RPG Maker MV"
    
    # Translation
    SOURCE_LANG: str = "auto"
    TARGET_LANG: str = "en"
    API: str = "google"
    API_KEY: str = ""
    API_URL: str = "https://openrouter.ai/api/v1/chat/completions" # This is used for custom API, ignored for built-in APIs like Google Translate
    max_workers: int = 4
    
    # Theme and UI
    language: str = "eng"
    dark_mode: bool = False
    theme: str = "default"
        
    def asdict(self) -> dict:
        return asdict(self)
    
    @staticmethod    
    def load(path: str|Path):
        try:
            with open(path, "r") as f:
                data = json.load(f, cls=JSONWithCommentsDecoder)
            return Settings(**data)
        except Exception as e:
            logger.error(f"Failed to load settings from {path}: {e}")
            return Settings()  # Return default settings on failure
    def save(self, path: str|Path="settings.json"):
        try:
            with open(path, "w") as f:
                json.dump(self.asdict(),  f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save settings to {path}: {e}")
            
    def __getitem__(self, key):
        return getattr(self, key)
    
    def __setitem__(self, key, value):
        setattr(self, key, value)
        
class PathSettingsLayout(QHBoxLayout):
    def __init__(self, default_path:str|Path, browse_type: str = "dir"):
        super().__init__()
        self.path_edit = QLineEdit()
        self.path_edit.setText(str(default_path))
        self.path_edit.setReadOnly(False)
        self.addWidget(self.path_edit)
        self.browse_button = QPushButton("Browse")
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
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings: Settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 270)        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the settings UI"""
        languages = ["en", "cht", "chs", "jp", "kor", "fra", "deu", "ru"]
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Translation Settings Tab
        translation_tab = QWidget()
        widgets = {"translator": {}, "UI": {}}
        layouts = {}
        ## dropdown Menus
        layouts["translator"] = QFormLayout(translation_tab)
        widgets["translator"]["SOURCE_LANG"] = QComboBox()
        widgets["translator"]["SOURCE_LANG"].addItems(['auto']+languages)
        widgets["translator"]["TARGET_LANG"] = QComboBox()
        widgets["translator"]["TARGET_LANG"].addItems(languages)
        widgets["translator"]["API"] = QComboBox()
        widgets["translator"]["API"].addItems(["Google", L["custom_api"]])
        ## Line Edits
        widgets["translator"]["API_KEY"] = QLineEdit(self.settings.API_KEY)
        widgets["translator"]["API_URL"] = QLineEdit(self.settings.API_URL)
        tabs.addTab(translation_tab, L["translator"])
        
        # UI Settings Tab
        ui_tab = QWidget()
        layouts["UI"] = QFormLayout(ui_tab)
        widgets["UI"]["language"] = QComboBox()
        widgets["UI"]["language"].addItems(languages)
        widgets["UI"]["language"].setCurrentText(self.settings.language)
        widgets["UI"]["dark_mode"] = QCheckBox()
        widgets["UI"]["dark_mode"].setChecked(self.settings.dark_mode)
        tabs.addTab(ui_tab, L["UI"])
        for layout_key, form_layout in layouts.items():
            for k, widget in widgets[layout_key].items():
                form_layout.addRow(L[k], widget)
        self.layouts = layouts
        self.widgets = widgets
        
        layout.addStretch()
        # Dialog buttons (OK/Cancel)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def save_settings(self):
        """Update settings from the dialog inputs"""
        for widgets in self.widgets.values():
            for k, widget in widgets.items():
                if isinstance(widget, QComboBox):
                    self.settings[k] = widget.currentText()
                elif isinstance(widget, QLineEdit):
                    self.settings[k] = widget.text().strip()
                elif isinstance(widget, QCheckBox):
                    self.settings[k] = widget.isChecked()