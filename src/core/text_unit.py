import logging
from typing import Optional
from dataclasses import dataclass, field

from .json_path import JsonPath, PathLike
from .translation.level import TranslationLevel
logger = logging.getLogger(__name__)

__all__ = ["TextUnit"]

@dataclass(slots=True)
class TextUnit:
    """ A class representing a single text unit that needs to be translated.
    
    Attributes:
        file (str): The name of the file containing the text unit.
        key (JsonPath): The unique identifier for the text unit, used to locate units in the file (e.g., JSON path, XML tag).
        original (str): The original text that needs to be translated.
        translation (Optional[str]): The translated text. If not provided, it defaults to the original text.
        level (TranslationLevel): The translation status of the text unit (e.g., untranslated, translated, reviewed).
        other_attrs (dict): A dictionary for any additional attributes related to the text unit.
    """
    file: str
    key: JsonPath
    original: str
    translation: str
    level: TranslationLevel = TranslationLevel.UNTRANSLATED
    other_attrs: dict = field(default_factory=dict)

    def __init__(
        self,
        file: str,
        key: PathLike,
        original: str,
        translation: Optional[str] = None,
        level: TranslationLevel = TranslationLevel.UNTRANSLATED,
        other_attrs: Optional[dict] = None,
        # consume any additional positional arguments to avoid errors and allow syntax `TextUnit(**row)` when row contains extra columns
        *args, 
        **kwargs
    ):
        self.file = file
        self.original = original
        self.translation = translation or original
        self.level = level
        self.other_attrs = other_attrs if other_attrs is not None else {}
        self.key = JsonPath(key)
    
    def asdict(self):
        # the asdict is slow internally
        return {
            "file": self.file,
            "key": self.key,
            "original": self.original,
            "translation": self.translation,
            "level": self.level.value,
            **self.other_attrs
        }