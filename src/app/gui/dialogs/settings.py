from pathlib import Path
from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QLabel, QTabWidget, 
    QVBoxLayout, QHBoxLayout,QFormLayout,
    QDialog, QFileDialog, QDialogButtonBox,
    QPushButton, QCheckBox, QComboBox,  QLineEdit,  
    QSpinBox, QDoubleSpinBox,
)
from app.settings import Settings
from app.locales import LanguagePack
from core.setting_space import SettingScope
from core.translation import Language, get_supported_languages, providers

L = LanguagePack()

class PathSettingsWidget(QWidget):
    """A reusable widget that combines a QLineEdit and a QPushButton to allow users to select a file or directory path."""    
    def __init__(self, default_path:str|Path, browse_type: str = "dir", browse_button_text: str = "Browse"):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(0)
        self.browse_type = browse_type
        self.path_edit = QLineEdit()
        self.path_edit.setText(str(default_path))
        self.path_edit.setReadOnly(False)
        self.browse_button = QPushButton(browse_button_text)
        self.browse_button.clicked.connect(self.browse_path)
        layout.addWidget(self.path_edit)
        layout.addWidget(self.browse_button)
        self.setLayout(layout)
        
    def text(self) -> str:
        return self.path_edit.text().strip()
    def setText(self, text:str):
        self.path_edit.setText(text)
    def browse_path(self):
        current_path = self.path_edit.text().strip()
        options = "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(
            None, L["file_dialog.select_file"], current_path,
            options
        )
        if path:
            self.path_edit.setText(path)

class CheckBoxLabel(QWidget):
    """A custom widget that groups a QCheckBox and a QLabel"""
    def __init__(self, text:str):
        super().__init__()
        self.setObjectName("CheckBoxLabelInstance")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.checkbox = QCheckBox()
        layout.addWidget(self.checkbox)
        label = QLabel(text)
        layout.addWidget(label)
        self.setLayout(layout)
    
    # Forward the checkbox methods and properties
    def isChecked(self) -> bool:
        return self.checkbox.isChecked()
    def setChecked(self, checked: bool):
        self.checkbox.setChecked(checked)
    @property
    def stateChanged(self):
        return self.checkbox.stateChanged
    @property
    def checkStateChanged(self):
        return self.checkbox.checkStateChanged
    def text(self) -> str:
        return self.checkbox.text()


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
        self.setWindowTitle(L["settings"])
        self.setMinimumSize(700, 270)
        self.init_ui()

    def update_lang_combobox(self, combo_box: QComboBox, current_lang:str, role:str, has_auto:bool=True):
        # prevent updating before the combo boxes are initialized
        api = self.widgets["translation"]["api_provider"].currentText()
        supported_langs: list[Language] = [Language(code="auto", name="Auto")] if has_auto else []
        if api in providers:
            if role == 'source':
                supported_langs.extend(get_supported_languages(self.settings.translation.api_provider, role='source'))
            elif role == 'target':
                supported_langs.extend(get_supported_languages(self.settings.translation.api_provider, role='target'))
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
        self.update_lang_combobox(self.widgets["translation"]["source_lang"], self.settings.translation.source_lang, role='source')
        self.update_lang_combobox(self.widgets["translation"]["target_lang"], self.settings.translation.target_lang, role='target', has_auto=False)

    def init_ui(self):
        """Initialize the settings UI"""
        # --- Create the main layout and tabs ---
        self.settings_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.settings_layout.addWidget(self.tabs)
        self.widgets: dict[str, dict[str, Any]] = {"translation": {}, "ui": {}, "dictionary": {}, "startup": {}, "workspace": {}}
        self.layouts: dict[str, QFormLayout] = {}
        self.use_local_checkboxes: dict[str, dict[str, CheckBoxLabel]] = {"translation": {}, "ui": {}, "dictionary": {}, "startup": {}, "workspace": {}}
        self.init_translation_settings_tab()
        self.init_ui_settings_tab()
        self.init_startup_settings_tab()
        self.init_workspace_settings_tab()        
        # --- Add checkboxes for each setting to switch local/global ---
        local_keys=self.settings.get_local_keys()
        for layout_key, form_layout in self.layouts.items():
            for k, widget in self.widgets[layout_key].items():
                if layout_key in {"startup", "workspace"}:
                    setting_key = k
                else:
                    setting_key = f"{layout_key}.{k}".lower()
                use_local_checkbox = CheckBoxLabel(L[f"settings.{layout_key}.{k}"])
                use_local_checkbox.setChecked(setting_key in local_keys)
                use_local_checkbox.setToolTip(L[f"settings.use_local.tooltip"])
                use_local_checkbox.checkStateChanged.connect(
                    lambda check, k=k, layout_key=layout_key: self.on_checkbox_state_changed(check, k, layout_key)
                )
                self.use_local_checkboxes[layout_key][k] = use_local_checkbox
                form_layout.addRow(use_local_checkbox, widget)
        # --- Add Ok & Cancel buttons at the bottom ---
        self.settings_layout.addStretch()
        # Dialog buttons (OK/Cancel)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.settings_layout.addWidget(button_box)
    
    def on_checkbox_state_changed(self, check, k, layout_key):
        """Switch the corresponding widget value between local and global settings based on the checkbox state."""
        key = f"{layout_key}.{k}".lower() if layout_key not in {"startup", "workspace"} else k
        if check == Qt.CheckState.Checked:
            v = self.settings.get_raw(key, scope=SettingScope.LOCAL)
        else:
            v = self.settings.get_raw(key, scope=SettingScope.GLOBAL)
        widget = self.widgets[layout_key][k]
        if isinstance(widget, QComboBox,):
            widget.setCurrentText(v or "")
        elif isinstance(widget, (QLineEdit, PathSettingsWidget)):
            widget.setText(v or "")
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(v) if v is not None else 0)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(v))
        else:
            raise TypeError(f"Unsupported widget type for setting '{k}': {type(widget)}")
        
    def init_startup_settings_tab(self):
        startup_tab = QWidget()
        self.layouts["startup"] = QFormLayout(startup_tab)
        self.widgets["startup"]["restore_last_session"] = QCheckBox()
        self.widgets["startup"]["restore_last_session"].setChecked(self.settings.restore_last_session)
        self.tabs.addTab(startup_tab, L["settings.startup"])
    
    def init_translation_settings_tab(self):
        translation_tab = QWidget()
        ## dropdown Menus
        self.layouts["translation"] = QFormLayout(translation_tab)
        self.widgets["translation"]["source_lang"] = QComboBox()
        self.widgets["translation"]["target_lang"] = QComboBox()
        self.widgets["translation"]["api_provider"] = QComboBox()
        self.widgets["translation"]["api_provider"].addItems([L[p] for p in providers.keys()])
        self.widgets["translation"]["api_provider"].setCurrentText(self.settings.translation.api_provider)
        self.widgets["translation"]["api_provider"].currentTextChanged.connect(self.on_api_changed)
        # Update language combo boxes based on the current API setting
        self.update_lang_combobox(self.widgets["translation"]["source_lang"], self.settings.translation.source_lang, role='source')
        self.update_lang_combobox(self.widgets["translation"]["target_lang"], self.settings.translation.target_lang, role='target', has_auto=False)

        ## Line Edits
        self.widgets["translation"]["custom_api_url"]   = QLineEdit(self.settings.translation.custom_api_url)
        self.widgets["translation"]["custom_api_model"] = QLineEdit(self.settings.translation.custom_api_model)
        self.widgets["translation"]["custom_api_key"]   = QLineEdit(self.settings.translation.custom_api_key)
        self.widgets["translation"]["deepl_api_key"]    = QLineEdit(self.settings.translation.deepl_api_key)
        self.widgets["translation"]["deepl_api_key"].setPlaceholderText(L["settings.translation.deepl_api_key.hint"])
        self.widgets["translation"]["custom_api_key"].setPlaceholderText(L["settings.translation.custom_api_key.hint"])
        self.tabs.addTab(translation_tab, L["settings.translation"])
    def init_ui_settings_tab(self):
        languages = L.get_available_languages()
        # UI Settings Tab
        ui_tab = QWidget()
        self.layouts["ui"] = QFormLayout(ui_tab)
        self.widgets["ui"]["language"] = QComboBox()
        self.widgets["ui"]["language"].addItems(languages)
        self.widgets["ui"]["language"].setCurrentText(self.settings.ui.language)
        self.widgets["ui"]["font_size"] = QSpinBox()
        self.widgets["ui"]["font_size"].setRange(8, 24)
        self.widgets["ui"]["font_size"].setValue(self.settings.ui.font_size)
        self.widgets["ui"]["dark_mode"] = QCheckBox()
        self.widgets["ui"]["dark_mode"].setChecked(self.settings.ui.dark_mode)
        self.tabs.addTab(ui_tab, L["settings.ui"])
    
    def init_workspace_settings_tab(self):
        from plugins import plugin_list
        workspace_tab = QWidget()
        self.layouts["workspace"] = QFormLayout(workspace_tab)
        # use raw directories from workspace_dir directly, preventing translating replacers such as %CWD% and %WORKSPACE_DIR%
        self.widgets["workspace"]["workspace_dir"] = PathSettingsWidget(self.settings.get_raw("workspace_dir"), "dir", L["browse"])
        self.widgets["workspace"]["game_data_dir"] = PathSettingsWidget(self.settings.get_raw("game_data_dir"), "dir", L["browse"])
        self.widgets["workspace"]["user_dict_dir"] = PathSettingsWidget(self.settings.get_raw("user_dict_dir"), "dir", L["browse"])
        self.widgets["workspace"]["output_dir"]    = PathSettingsWidget(self.settings.get_raw("output_dir"   ), "dir", L["browse"])
        self.widgets["workspace"]["plugin"] = QComboBox()
        self.widgets["workspace"]["plugin"].addItems(plugin_list)
        self.widgets["workspace"]["plugin"].setCurrentText(self.settings.plugin)
        self.tabs.addTab(workspace_tab, L["settings.workspace"])

    def save_settings(self):
        """Update settings from the dialog inputs
        
        Based on the use_local_checkboxes checked state, the settings will be saved to either local or global settings.
        """
        for tab, widgets in self.widgets.items():
            tab = tab.lower()
            k, v = None, None
            for k, widget in widgets.items():
                key = f"{tab}.{k}".lower() if tab not in {"startup", "workspace"} else k
                if k in ["source_lang", "target_lang"]:
                    v = widget.currentData()  # Get the language code from the combo box
                elif isinstance(widget, QComboBox):
                    v = widget.currentText()
                elif isinstance(widget, (QLineEdit, PathSettingsWidget)):
                    v = widget.text().strip()
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    v = widget.value()
                elif isinstance(widget, QCheckBox):
                    v = widget.isChecked()
                else:
                    raise TypeError(f"Unsupported widget type for setting '{k}': {type(widget)}")
                if k is not None and v is not None:
                    if self.use_local_checkboxes[tab][k].isChecked(): 
                        # use local settings
                        self.settings.set_val(key, v, scope=SettingScope.LOCAL) 
                    else: # use global settings
                        self.settings.set_val(key, v, scope=SettingScope.GLOBAL)
