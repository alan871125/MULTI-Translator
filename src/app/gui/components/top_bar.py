import logging
from pathlib import Path
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QComboBox
from PyQt5.QtCore import pyqtSignal
import engines

logger = logging.getLogger(__name__)

class TopBar(QWidget):
    """
    Top bar component containing workspace selection, engine selection, and filtering.
    """
    filter_clicked = pyqtSignal()
    workspace_clicked = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.widgets = {}
        self.init_ui()
        
        # Connect to settings signals
        if self.settings:
            self.settings.workspace_changed.connect(self.refresh)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.widgets['filter_button'] = QPushButton("Filter", self)
        self.widgets['filter_button'].clicked.connect(self.filter_clicked.emit)
        
        current_workspace = Path(self.settings.workspace_dir or "Default").name
        self.widgets['workspace_button'] = QPushButton(current_workspace, self)
        self.widgets['workspace_button'].clicked.connect(self.workspace_clicked.emit)
        
        self.widgets['engine_select'] = QComboBox()
        self.widgets['engine_select'].addItems(engines.supported_engines)
        self.widgets['engine_select'].setCurrentText(self.settings.engine)
        self.widgets['engine_select'].currentTextChanged.connect(
            lambda text: setattr(self.settings, 'engine', text)
        )
        
        for widget in self.widgets.values():
            layout.addWidget(widget)

    def refresh(self, *args, **kwargs):
        """Refresh the UI state from settings."""
        current_workspace = Path(self.settings.workspace_dir or "Default").name
        self.widgets['workspace_button'].setText(current_workspace)
        self.widgets['engine_select'].setCurrentText(self.settings.engine)
        logger.debug('Top bar refreshed with current workspace and engine.')
