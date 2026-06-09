from dataclasses import dataclass, field, asdict
import json

from .translation.level import TranslationLevel

class JsonPath(str):
    @classmethod
    def from_list(cls, json_path_list: list[str|int]):
        return cls(json.dumps(json_path_list))
    def to_list(self):
        return json.loads(self)
    def __add__(self, other: 'JsonPath'):
        return JsonPath(self[:-1] + "," + other[1:])  # Combine two JSON paths by merging their list representations
    
@dataclass
class TextUnit:
    """ A class representing a single text unit that needs to be translated.
    
    Attributes:
        file (str): The name of the file containing the text unit.
        id (str): The unique identifier for the text unit.
        field (str): The specific field within the file where the text unit is located.
        original (str): The original text that needs to be translated.
        translation (str): The translated text, initially empty.
        json_path (JsonPath|None): The path within the JSON structure to locate this text unit, used for updating translations back into the JSON.
    """
    file: str
    id: str
    attribute: str
    original: str
    translation: str = ""
    json_path: JsonPath|None = None
    level: TranslationLevel = TranslationLevel.UNTRANSLATED
    
    def update_translation(self, new_translation: str):
        # TODO: Implement
        self.translation = new_translation
        if self.json_path:
            # Update the translation in the JSON structure
            pass

    def asdict(self):
        return asdict(self)