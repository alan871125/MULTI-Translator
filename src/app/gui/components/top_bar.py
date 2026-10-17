import logging
from pathlib import Path
from typing import Hashable, Optional

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QComboBox, QButtonGroup
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap, QFont
from PySide6.QtSvg import QSvgRenderer

from qt_extensions.widgets import PieChartWidget

from plugins import plugin_list
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
    pixmap.fill(Qt.GlobalColor.transparent)  # Start with a transparent pixmap
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
        self.buttons.setObjectName("LevelFilterButtonsGroup")
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
            
class ProgressPieChart(PieChartWidget):
    """A pie chart widget to visualize translation progress."""
    def __init__(self, parent=None):
        super().__init__(num_segments=len(TranslationLevel)-1, sum_proportion=None, parent=parent)
        self.setFixedSize(50, 50)  # Set a fixed size for the pie chart
        self.setToolTip("Translation Progress")
        
        self.set_style(bar_width=10, center_label=True, center_label_font=QFont("Arial", 8, QFont.Weight.Bold))
        self.level_map = {lv: i for i, lv in enumerate(TranslationLevel) if lv != TranslationLevel.UNTRANSLATED}
        self.SEGMENT_COLORS = [ThemeManager.theme.get_level_color(lv) for lv in TranslationLevel if lv!= TranslationLevel.UNTRANSLATED]
        
    def update_values(self, counts:dict[Hashable, int]):
        """Update the pie chart based on the provided counts of translation levels."""
        values = [counts.get(lv, 0) for lv in TranslationLevel if lv!= TranslationLevel.UNTRANSLATED]
        self.set_values(values)
        
class TopBar(QWidget):
    """
    Top bar component containing workspace selection, engine selection, and filtering.
    """
    filter_clicked = Signal()
    workspace_clicked = Signal()

    def __init__(self, settings:Settings, table_filters:Optional[TableFilters]=None, parent=None):
        super().__init__(parent)
        self.settings: Settings = settings
        self.init_ui(table_filters or TableFilters())
        
        # Connect to settings signals
        if self.settings:
            self.settings.workspace_changed.connect(self.refresh)

    def init_ui(self, table_filters:TableFilters):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.filter_button = QPushButton(L["filter"], self)
        self.filter_button.clicked.connect(self.filter_clicked.emit)
                
        self.lv_buttons = LevelFilterButtons(table_filters, parent=self)
        self.workspace_button = QPushButton(self.settings.workspace_name, self)
        self.workspace_button.clicked.connect(self.workspace_clicked.emit)
        
        self.engine_combo_box = QComboBox()
        self.engine_combo_box.addItems(plugin_list)
        self.engine_combo_box.setCurrentText(self.settings.plugin)
        self.engine_combo_box.currentTextChanged.connect(
            lambda text: setattr(self.settings, 'plugin', text)
        )
        self.progress_chart = ProgressPieChart(self)
        layout.addWidget(self.filter_button)
        layout.addWidget(self.lv_buttons)
        layout.addWidget(self.engine_combo_box)
        layout.addWidget(self.workspace_button)
        layout.addWidget(self.progress_chart)
            
    def refresh(self, *args, **kwargs):
        """Refresh the UI state from settings."""
        self.workspace_button.setText(self.settings.workspace_name)
        self.engine_combo_box.setCurrentText(self.settings.plugin)
        
    def set_source_filters(self, filters:TableFilters):
        """Update the level filter buttons based on the provided TableFilters instance."""
        self.lv_buttons.set_source_filters(filters)
        