import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QComboBox, QButtonGroup
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer
import core.engines as engines
from core.translation import TranslationLevel
from app.settings import Settings
from app.gui.dialogs.search import TableFilters
from app.language import LanguagePack
from ..theme import ThemeManager

logger = logging.getLogger(__name__)
L = LanguagePack()

BUTTON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" fill="{color}" />
</svg>"""

def create_color_icon(color:str, size:int=24) -> QIcon:
    """Creates a circular icon of the specified color and size."""
    svg_data = BUTTON.format(color=color)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)  # Start with a transparent pixmap
    renderer = QSvgRenderer(bytearray(svg_data, encoding='utf-8'))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap.scaled(size, size))

class LevelFilterButtons(QWidget):
    """A button group for filtering translation units by translation level"""
    def __init__(self, filters:TableFilters, parent:Optional[QWidget]=None, button_size:int=24):
        super().__init__(parent)
        self.buttons = QButtonGroup(self)
        self.buttons.setExclusive(False)
        self.filters = filters
        theme = ThemeManager.theme
        layout = QHBoxLayout(self)
        for level in TranslationLevel:
            color = theme.get_level_color(level)
            icon = create_color_icon(color, size=int(button_size*0.8))  # Slightly smaller than button size for padding
            button = QPushButton("", self)
            button.setIcon(icon)
            button.setCheckable(True)
            button.setChecked(True)  # Start with all levels checked
            button.setToolTip(L[f"button.{level.name.lower()}.tooltip"])
            layout.addWidget(button)
            self.buttons.addButton(button, level.value)
            
            button.setFixedSize(button_size, button_size)
            button.setStyleSheet(f"""QPushButton{{
                border-width: 1px;
                border-radius: 6px;
            }}
            QPushButton:checked{{
                background-color: {theme.SELECT_COLOR};
            }}
            QPushButton:hover{{
                background-color: {theme.HOVER_COLOR};
            }}
            """)
        self.buttons.buttonToggled.connect(self.on_button_toggled)

    def on_button_toggled(self, button:QPushButton, checked):
        lv = TranslationLevel(self.buttons.id(button))
        self.filters.set_level([lv], checked)
        pass
    
    def set_source_filters(self, filters:TableFilters):
        """Update the button states based on the provided TableFilters instance."""
        self.filters = filters
        from app.translation_table import TranslationTableModel
        if isinstance(parent := filters.parent(), TranslationTableModel):
            logger.debug(f"Updating LevelFilterButtons based on new TableFilters: {filters}, parent: {parent.file_path}")
        for button in self.buttons.buttons():
            lv = TranslationLevel(self.buttons.id(button))
            button.setChecked(self.filters.levels.get(lv, True))  # Default to True if not found

class TopBar(QWidget):
    """
    Top bar component containing workspace selection, engine selection, and filtering.
    """
    filter_clicked = pyqtSignal()
    workspace_clicked = pyqtSignal()

    def __init__(self, settings:Settings, table_filters:Optional[TableFilters]=None, parent=None):
        super().__init__(parent)
        self.settings: Settings = settings
        self.widgets = {}
        self.init_ui(table_filters or TableFilters())
        
        # Connect to settings signals
        if self.settings:
            self.settings.workspace_changed.connect(self.refresh)

    def init_ui(self, table_filters:TableFilters):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.widgets['filter_button'] = QPushButton("Filter", self)
        self.widgets['filter_button'].clicked.connect(self.filter_clicked.emit)
                
        self.widgets['level_filters'] = LevelFilterButtons(table_filters, parent=self)
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
            
    @property
    def lv_buttons(self)-> LevelFilterButtons:
        return self.widgets['level_filters']
    
    def refresh(self, *args, **kwargs):
        """Refresh the UI state from settings."""
        current_workspace = Path(self.settings.workspace_dir or "Default").name
        self.widgets['workspace_button'].setText(current_workspace)
        self.widgets['engine_select'].setCurrentText(self.settings.engine)
        
    def set_source_filters(self, filters:TableFilters):
        """Update the level filter buttons based on the provided TableFilters instance."""
        self.widgets['level_filters'].set_source_filters(filters)
        