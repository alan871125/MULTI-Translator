import re
import logging
import PySide6.QtWidgets as qt
from dataclasses import dataclass, asdict
from pathlib import Path
from core.translation.level import TranslationLevel

logger = logging.getLogger(__name__)
BASE_THEME = Path(__file__).parent / "styles" / "base.qss"
VAR_PATTERN = re.compile(r"\$([A-Z_]+)")

@dataclass
class Theme:
    BACKGROUND_COLOR:str = "#f0f0f0"
    MAIN_CONTENT_COLOR:str = "#ffffff"
    ALT_CONTENT_COLOR:str = "#f8f8f8"
    BORDER_COLOR:str = "#cccccc"
    TEXT_COLOR:str = "#000000"
    DISABLED_COLOR:str = "#999999"
    HOVER_COLOR:str = "rgba(85, 148, 230, 0.25)"
    HOVER_BORDER_COLOR:str = "rgba(85, 148, 230, 0.5)"
    SELECT_COLOR:str = "rgba(0, 100, 255, .2)" # Semi-transparent selection color
    SELECT_BORDER_COLOR:str = "rgba(85, 148, 230, 0.5)"
    SCROLLBAR_HANDLE_COLOR:str = "#b0b0b0"
    BUTTON_RADIUS:str = "4px"
    BUTTON_COLOR:str = "#FFFFFF"
    FONT_FAMILY: str = "Microsoft JhengHei, Microsoft YaHei, Arial, sans-serif"
    FONT_SIZE: str = "11pt"
    LV_UNTRANSLATED:str = ""
    LV_PARTIAL: str ="#f39292"
    LV_HEURISTIC: str ="#f493da"
    LV_BATCH: str ="#aa87ce"
    LV_DICTIONARY: str ="#98b9f3"
    LV_API: str ="#ace3e1"
    LV_VERIFIED: str ="#a0f5a2"
    LV_LOCKED: str = "#fdd939"
    USE_COLOR_LEVEL_BACKGROUND: bool = True # If true, use background color to indicate translation level; if false, use text color
    PADDING_X: str = "6px"
    PADDING_Y: str = "2px"
    def __post_init__(self):
        if not self.LV_UNTRANSLATED:
            self.LV_UNTRANSLATED = self.MAIN_CONTENT_COLOR
    def asdict(self)->dict:
        return asdict(self)
    def get_level_color(self, level: TranslationLevel):
        return getattr(self, f"LV_{level.name}", self.LV_UNTRANSLATED)

LIGHT = Theme()
DARK = Theme(
    BACKGROUND_COLOR = "#2b2b2b",
    MAIN_CONTENT_COLOR = "#232323",
    ALT_CONTENT_COLOR = "#272727",
    BORDER_COLOR = "#333333",
    TEXT_COLOR = "#F5F5F5",
    DISABLED_COLOR = "#777777",
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
    @classmethod
    def set_theme(cls, theme: Theme|None = None, dark=False, **kwargs:str):
        if theme is not None:
            cls.theme = theme
        elif dark:
            cls.theme = DARK
        else:
            cls.theme = LIGHT
        if kwargs:
            for key, value in kwargs.items():
                setattr(cls.theme, key, value)
        cls.apply_theme()

    @classmethod
    def apply_theme(cls):
        app = qt.QApplication.instance()
        if isinstance(app, qt.QApplication):
            app.setStyleSheet(cls.generate_theme())
        else:
            logger.error("No QApplication instance found. Cannot apply theme.")
    
    @classmethod
    def generate_theme(cls) -> str:
        """Generate a dark theme stylesheet based on the defined colors and fonts."""
        base_theme = BASE_THEME.read_text(encoding="utf-8")
        theme_dict = cls.theme.asdict()
        theme = VAR_PATTERN.sub(lambda m: theme_dict[m.group(1)], base_theme)
        return theme
