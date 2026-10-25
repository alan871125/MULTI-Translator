from app.settings import L, Settings

from PySide6.QtWidgets import QLabel, QDialog, QDialogButtonBox, QVBoxLayout, QPlainTextEdit
from PySide6.QtGui import QShortcut, QKeySequence

from app.settings import Settings
from app.locales import LanguagePack
L = LanguagePack()

class TranslationDialog(QDialog):
    """Translation dialog window"""
    def __init__(self, settings: Settings, original:str = "", translation:str = "", parent=None):
        super().__init__(parent)
        self.settings: Settings = settings
        self.setWindowTitle(L["translation"])
        self.setMinimumSize(700, 270)
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # show the original text in a box that is read-only, and the translated text in a box that is editable
        self.original_text_edit = QPlainTextEdit()
        self.original_text_edit.setReadOnly(True)
        self.original_text_edit.setPlainText(original)
        self.translated_text_edit = QPlainTextEdit()
        self.translated_text_edit.setPlainText(translation)

        layout.addWidget(QLabel(L["original"]))
        layout.addWidget(self.original_text_edit)
        layout.addWidget(QLabel(L["translation"]))
        layout.addWidget(self.translated_text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # add a keyboard shortcut for Ctrl+Enter to accept the dialog
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self.accept)
        
        self.translated_text_edit.setFocus() # set focus to the translated text edit so the user can start typing immediately
        
    @property
    def original(self) -> str:
        return self.original_text_edit.toPlainText()
    @property
    def translation(self) -> str:
        return self.translated_text_edit.toPlainText()
        
    