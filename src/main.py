from app.gui.main_window import TranslationApp
import sys
import PyQt5.QtWidgets as qt
from app.settings import Settings

if __name__ == "__main__":
    settings = Settings.load("settings.json")
    darkmode = int(settings.dark_mode)
    app = qt.QApplication(sys.argv+['-platform', f'windows:darkmode={darkmode}'])
    translator = TranslationApp(settings)
    translator.show()
    app.exec_()