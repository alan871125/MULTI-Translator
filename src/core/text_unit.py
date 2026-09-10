from dataclasses import dataclass, field, asdict
from .json_path import JsonPath
from .translation.level import TranslationLevel

@dataclass(slots=True)
class TextUnit:
    """ A class representing a single text unit that needs to be translated.
    
    Attributes:
        file (str): The name of the file containing the text unit.
        key (JsonPath): The unique identifier for the text unit, used to locate units in the file (e.g., JSON path, XML tag).
        original (str): The original text that needs to be translated.
        translation (str): The translated text, initially empty.
    """
    file: str
    key: JsonPath
    original: str
    translation: str = ""
    level: TranslationLevel = TranslationLevel.UNTRANSLATED
    
    other_attrs: dict = field(default_factory=dict)  # A dictionary to hold any additional attributes that may be needed for specific engines    

    def asdict(self):
        return asdict(self)