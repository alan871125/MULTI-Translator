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
    ALT_CONTENT_COLOR:str = "#f8f8f8"
    BORDER_COLOR:str = "#cccccc"
    TEXT_COLOR:str = "#000000"
    HOVER_COLOR:str = "rgba(85, 148, 230, 0.25)"
    HOVER_BORDER_COLOR:str = "rgba(85, 148, 230, 0.5)"
    SELECT_COLOR:str = "rgba(0, 100, 255, .2)" # Semi-transparent selection color
    SELECT_BORDER_COLOR:str = "rgba(85, 148, 230, 0.5)"
    SCROLLBAR_HANDLE_COLOR:str = "#b0b0b0"
    BUTTON_RADIUS:str = "2px"
    BUTTON_COLOR:str = "#FFFFFF"
    FONT_FAMILY: str = "Microsoft YaHei, PingFang SC, Arial"
    FONT_SIZE: str = "14px"
    LV_UNTRANSLATED:str = ""
    LV_API: str ="#aa87ce"
    LV_PARTIAL: str ="#f39292"
    LV_VERIFIED: str ="#a0f5a2"
    LV_DICTIONARY: str ="#98b9f3"
    LV_BATCH: str ="#f4ea80"
    LV_HEURISTIC: str ="#f2bc7e"
    USE_COLOR_LEVEL_BACKGROUND: bool = True # If true, use background color to indicate translation level; if false, use text color
    PADDING_X: str = "6px"
    PADDING_Y: str = "2px"
    def __post_init__(self):
        if not self.LV_UNTRANSLATED:
            self.LV_UNTRANSLATED = self.MAIN_CONTENT_COLOR
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
    HOVER_BORDER_COLOR = "rgba(85, 148, 230, 0.5)",
    SELECT_COLOR = "rgba(85, 148, 230, 0.25)",
    SCROLLBAR_HANDLE_COLOR = "#444444",
    BUTTON_COLOR = "#2f2f2f",
    LV_UNTRANSLATED = "#fcfcfc",
    # LV_UNTRANSLATED="#3d1b1b",
    # LV_API="#38224e",
    # LV_PARTIAL="#341524",
    # LV_VERIFIED="#153115",
    # LV_DICTIONARY="#162031",
    # LV_BATCH="#34321a",
    # LV_HEURISTIC="#3f2a1c",
    USE_COLOR_LEVEL_BACKGROUND = False,
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
            background-color: {BACKGROUND_COLOR} ;
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE};
            color: {TEXT_COLOR} ;
        }}
        """
    @classmethod
    def generate_theme(cls) -> str:
        """Generate a dark theme stylesheet based on the defined colors and fonts."""
        base_theme = BASE_THEME.read_text(encoding="utf-8") if BASE_THEME.exists() else ""
        for key, value in cls.theme.asdict().items():
            if isinstance(value, str):
                base_theme = base_theme.replace(f"${key}", value)
        theme = cls.get_global_style_theme()
        theme+="""
        
        
        QTableView::item:selected,
        QTableWidget::item:selected {{
            background-color: {SELECT_COLOR};
            border: 1px solid {SELECT_BORDER_COLOR};
            color: {TEXT_COLOR};
        }}        
        QTableCornerButton::section,
        QHeaderView::section {{
            background-color: {BACKGROUND_COLOR};
            padding: 4px 6px;
            border: 1px solid {BORDER_COLOR};
        }}    
        QLineEdit, QPlainTextEdit, QTextEdit,
        QSpinBox, QComboBox {{
            background-color: {MAIN_CONTENT_COLOR};
            border: 1px solid {BORDER_COLOR};
            border-radius: 4px;
            padding: 2px 6px;
        }}
        QSpinBox:hover, QComboBox:hover{{
            background-color: {HOVER_COLOR};
            border: 1px solid {HOVER_BORDER_COLOR};          
        }}
        QSpinBox::up-button, QSpinBox::down-button, QComboBox::drop-down {{
            border: none;
        }}
        QSpinBox::down-arrow, QComboBox::down-arrow {{
            image: url(:/assets/resources/icons/chevron-down.svg);
            width: 12px;
            height: 12px;
        }}
        QSpinBox::up-arrow, QComboBox::up-arrow {{
            image: url(:/assets/resources/icons/chevron-up.svg);
            width: 12px;
            height: 12px;
        }}
        
        QTabWidget::pane {{
            background-color: {BACKGROUND_COLOR};
            border-top: 1px solid {BORDER_COLOR};
        }}        
        QTabBar::tab {{
            background: {BACKGROUND_COLOR};
            border: 1px solid {BORDER_COLOR};
            padding: {PADDING_Y} {PADDING_X};
            margin-right: 1px;
            border-bottom: none;
            border-top-left-radius:  4px;
            border-top-right-radius: 4px;
        }}
        QPushButton {{
            border-radius: {BUTTON_RADIUS};
            background-color: {BUTTON_COLOR};
            border: 1px solid {BORDER_COLOR};
            padding: {PADDING_Y} {PADDING_X};
        }}    
        QMenu::item:selected,
        QMenuBar::item:selected,
        QTabBar::tab:selected,
        QPushButton:selected {{
            background-color: {SELECT_COLOR};
            border: 1px solid {SELECT_BORDER_COLOR};
            border-radius: {BUTTON_RADIUS};
        }}
        CustomContextMenu::item:hover,
        QMenuBar::item:hover,
        QTabBar::tab:hover,
        QPushButton:hover {{
            background-color: {HOVER_COLOR};
            border: 1px solid {HOVER_BORDER_COLOR};
            border-radius: {BUTTON_RADIUS};
        }}
        """
        return base_theme+theme.format_map(cls.theme.asdict())
