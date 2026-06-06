from dataclasses import dataclass, field, asdict
from typing import Any
from .translation_level import TranslationLevel
@dataclass
class TextUnit:
    """ A class representing a single text unit that needs to be translated.
    
    Attributes:
        file (str): The name of the file containing the text unit.
        id (str): The unique identifier for the text unit.
        field (str): The specific field within the file where the text unit is located.
        original (str): The original text that needs to be translated.
        translation (str): The translated text, initially empty.
        json_path (list): The path within the JSON structure to locate this text unit, used for updating translations back into the JSON.
    """
    file: str
    id: str
    attribute: str
    original: str
    translation: str = ""
    json_path: list = field(default_factory=list)
    level: TranslationLevel = TranslationLevel.UNTRANSLATED
    def update_translation(self, new_translation: str):
        # TODO: Implement
        self.translation = new_translation
        if self.json_path:
            # Update the translation in the JSON structure
            pass

    def asdict(self):
        return asdict(self)