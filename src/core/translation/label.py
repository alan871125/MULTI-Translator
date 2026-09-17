from enum import Enum
class TranslationLabel(Enum):
    NEW = "NEW"
    DEPRECATED = "DEPRECATED"
    UPDATED = "UPDATED"
    def __str__(self):
        return self.value
