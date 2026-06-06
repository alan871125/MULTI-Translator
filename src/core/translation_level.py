from enum import Enum, auto
class TranslationLevel(Enum):
    UNTRANSLATED = auto()
    HEURISTIC = auto()
    PARTIAL = auto()
    DICTIONARY = auto()
    API = auto()
    VERIFIED = auto()