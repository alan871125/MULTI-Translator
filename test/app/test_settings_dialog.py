
from pytestqt.qtbot import QtBot
from PySide6.QtCore import Qt
from app.gui.dialogs.settings import SettingsDialog
from app.settings import Settings, AppSettings
from core.setting_space import SettingScope
from app.locales import LanguagePack

L = LanguagePack()

class TestSettingsDialog:
    def test_use_local_checkbox(self, qtbot: QtBot, tmp_settings: Settings):
        # Open the settings dialog
        default_provider = AppSettings.TranslationSettings.model_fields['api_provider'].default
        assert tmp_settings.translation.api_provider == default_provider
        tmp_settings.set_val("translation.api_provider", "deepl", scope=SettingScope.LOCAL)
        dialog = SettingsDialog(settings=tmp_settings)
        dialog.show() # this prevents the mouse click being dropped
        use_local_checkbox = dialog.use_local_checkboxes['translation']['api_provider']
        assert dialog.widgets['translation']['api_provider'].currentText() == L["deepl"]
        assert use_local_checkbox.isChecked() == True
        qtbot.addWidget(dialog)
        # click the "Use Local" checkbox for translation.api_provider
        with qtbot.waitSignal(use_local_checkbox.checkStateChanged):
            qtbot.mouseClick(
                use_local_checkbox.checkbox, 
                Qt.MouseButton.LeftButton
            )
        assert use_local_checkbox.isChecked() == False
        assert dialog.widgets['translation']['api_provider'].currentText() == L[default_provider]
        