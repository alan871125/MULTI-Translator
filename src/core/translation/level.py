from enum import IntEnum, auto
class TranslationLevel(IntEnum):
    UNTRANSLATED = 0
    HEURISTIC = auto()
    PARTIAL = auto()
    DICTIONARY = auto()
    API = auto()
    VERIFIED = auto()
    LOCKED = -1