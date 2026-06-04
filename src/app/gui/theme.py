import logging
import PyQt5.QtWidgets as qt
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import cast
logger = logging.getLogger(__name__)
BASE_THEME = Path(__file__).parent / "styles" / "base.qss"

@dataclass
class Theme:
    BACKGROUND_COLOR:str = "#f0f0f0"
    MAIN_CONTENT_COLOR:str = "#ffffff"
    ALT_CONTENT_COLOR:str = "#fcfcfc"
    BORDER_COLOR:str = "#cccccc"
    TEXT_COLOR:str = "#000000"
    HOVER_COLOR:str = "#e0e0e0"
    SELECTION_COLOR:str = "#5594d3"
    SCROLLBAR_HANDLE_COLOR:str = "#b0b0b0"
    BUTTON_RADIUS:str = "4px"
    BUTTON_COLOR:str = "#e1e1e1"
    FONT_FAMILY: str = "Segoe UI, sans-serif"
    FONT_SIZE: str = "14px"
    LV_UNTRANSLATED: str ="#f0f0f0"
    LV_API: str ="#aa87ce"
    LV_PARTIAL: str ="#f39292"
    LV_VERIFIED: str ="#a0f5a2"
    LV_DICTIONARY: str ="#98b9f3"
    LV_BATCH: str ="#f4ea80"
    LV_HEURISTIC: str ="#f2bc7e"
    USE_COLOR_LEVEL_BACKGROUND: bool = True # If true, use background color to indicate translation level; if false, use text color
    def asdict(self)->dict:
        return asdict(self)
    def get_level_color(self, level:str):
        return getattr(self, f"LV_{level.upper()}", self.LV_UNTRANSLATED)


LIGHT = Theme()
DARK = Theme(
    BACKGROUND_COLOR = "#2b2b2b",
    MAIN_CONTENT_COLOR = "#232323",
    ALT_CONTENT_COLOR = "#272727",
    BORDER_COLOR = "#333333",
    TEXT_COLOR = "#ffffff",
    HOVER_COLOR = "#5c5c5c",
    SELECTION_COLOR = "#555555",
    SCROLLBAR_HANDLE_COLOR = "#444444",
    BUTTON_RADIUS = "2px",
    BUTTON_COLOR = "#2f2f2f",
    FONT_FAMILY = "Segoe UI, sans-serif",
    FONT_SIZE = "14px",
    # LV_UNTRANSLATED="#3d1b1b",
    # LV_API="#38224e",
    # LV_PARTIAL="#341524",
    # LV_VERIFIED="#153115",
    # LV_DICTIONARY="#162031",
    # LV_BATCH="#34321a",
    # LV_HEURISTIC="#3f2a1c",
    USE_COLOR_LEVEL_BACKGROUND = False
)

class ThemeManager:
    """Manage and generate themes for the application. """

    theme: Theme = DARK
    @classmethod
    def set_theme(cls, theme: Theme|None = None, dark=False):
        if theme is not None:
            cls.theme = theme
        elif dark:
            cls.theme = DARK
        else:
            cls.theme = LIGHT
        cls.apply_theme()
    @classmethod
    def apply_theme(cls):
        if (app := qt.QApplication.instance()) is None:
            return
        # Cast to QApplication so static type checkers know setStyleSheet exists
        app_qt = cast(qt.QApplication, app)
        app_qt.setStyleSheet(cls.generate_theme())
    @classmethod  
    def get_global_style_theme(cls) -> str:
        return """* {{
            background-color: {BACKGROUND_COLOR} !important;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE};
            color: {TEXT_COLOR} !important;
        }}
        """.format_map(cls.theme.asdict())
    @classmethod
    def generate_theme(cls) -> str:
        """Generate a dark theme stylesheet based on the defined colors and fonts."""
        theme = BASE_THEME.read_text(encoding="utf-8") if BASE_THEME.exists() else ""
        for key, value in cls.theme.asdict().items():
            if isinstance(value, str):
                theme = theme.replace(f"${key}", value)
        theme += cls.get_global_style_theme()
        return theme+"""
        QTableView {{
            background-color: {MAIN_CONTENT_COLOR};
            qproperty-alternatingRowColors: true;
        }}
        QTableView::item:alternate {{
            background-color: {ALT_CONTENT_COLOR};
        }}
        QTableView::item:selected,
        QTableWidget::item:selected {{
            background-color: {SELECTION_COLOR} !important;
            color: {TEXT_COLOR} !important;
        }}        
        QTableCornerButton::section,
        QHeaderView::section {{
            background-color: {BACKGROUND_COLOR};
            padding: 4px 6px;
            border: 1px solid {BORDER_COLOR};
        }}        
        QPushButton {{
            border-radius: {BUTTON_RADIUS};
            background-color: {BUTTON_COLOR};
            border: 1px solid {BORDER_COLOR};
        }}        
        QLineEdit, QPlainTextEdit, QTextEdit,
        QComboBox {{
            background-color: {MAIN_CONTENT_COLOR};
            border: 1px solid {BORDER_COLOR};
            border-radius: 4px;
            padding: 2px 6px;
        }}
        
        QTabWidget::pane {{
            background-color: {BACKGROUND_COLOR};
            border-top: 1px solid {BORDER_COLOR};
        }}        
        QTabBar::tab {{
            background: {BACKGROUND_COLOR};
            border: 1px solid {BORDER_COLOR};
            padding: 6px 12px;
            margin-right: 2px;
            border-bottom: none;
            border-top-left-radius:  4px;
            border-top-right-radius: 4px;
        }}
        QMenu::item:selected,
        QMenuBar::item:selected,
        QTabBar::tab:selected,
        QPushButton:selected {{
            background: {SELECTION_COLOR};
        }}
        CustomContextMenu::item:hover,
        QMenuBar::item:hover,
        QTabBar::tab:hover,
        QPushButton:hover {{
            background: {HOVER_COLOR};
        }}
        """.format_map(cls.theme.asdict())
        
