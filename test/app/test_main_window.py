from pytestqt.qtbot import QtBot
from unittest.mock import MagicMock, patch
from pathlib import Path
from PySide6.QtCore import Qt
from app.gui.main_window import TranslationApp

def test_load_file_signal(qtbot: QtBot, main_window:TranslationApp):
    # click the "Open File" button
    test_file = Path("test/.data/simple_json/test1.json").absolute().as_posix()
    
    # main_window.load_file_requested
    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(test_file, "JSON Files (*.json)")
    ):
        with qtbot.waitSignal(main_window.load_file_requested, timeout=1000) as blocker:
            # Trigger the open file handler on the UI
            main_window.request_load_file()
        assert blocker.args == [test_file]
