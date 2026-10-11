from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget

from app.settings import L, Settings
from core.translation import Language, get_supported_languages, providers


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
        self.setWindowTitle(L["settings"])
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
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.settings_layout.addWidget(button_box)

    def init_startup_settings_tab(self):
        startup_tab = QWidget()
        self.layouts["startup"] = QFormLayout(startup_tab)
        self.widgets["startup"]["restore_last_session"] = QCheckBox()
        self.widgets["startup"]["restore_last_session"].setChecked(self.settings.restore_last_session)
        self.tabs.addTab(startup_tab, L["settings.startup"])

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
        from plugins import plugin_list
        workspace_tab = QWidget()
        self.layouts["workspace"] = QFormLayout(workspace_tab)
        # use raw directories from workspace_dir directly, preventing translating replacers such as %CWD% and %WORKSPACE_DIR%
        self.widgets["workspace"]["workspace_dir"] = PathSettingsLayout(self.settings.workspace_data.workspace_dir or "./", browse_type="dir")
        self.widgets["workspace"]["game_data_dir"] = PathSettingsLayout(self.settings.workspace_data.game_data_dir, browse_type="dir")
        self.widgets["workspace"]["user_dict_dir"] = PathSettingsLayout(self.settings.workspace_data.user_dict_dir, browse_type="dir")
        self.widgets["workspace"]["output_dir"] = PathSettingsLayout(self.settings.output_dir, browse_type="dir")
        self.widgets["workspace"]["engine"] = QComboBox()
        self.widgets["workspace"]["engine"].addItems(plugin_list)
        self.widgets["workspace"]["engine"].setCurrentText(self.settings.plugin)
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