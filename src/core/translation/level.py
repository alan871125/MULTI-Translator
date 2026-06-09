from enum import IntEnum, auto
class TranslationLevel(IntEnum):
    UNTRANSLATED = auto()
    HEURISTIC = auto()
    PARTIAL = auto()
    DICTIONARY = auto()
    API = auto()
    VERIFIED = auto()