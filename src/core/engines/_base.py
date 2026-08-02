import logging
from pathlib import Path
from typing import ClassVar, Optional, Protocol, Sequence
from abc import ABC, abstractmethod
from core.text_unit import TextUnit

logger = logging.getLogger(__name__)

class SupportedDirType(ABC, str):
    @classmethod
    @abstractmethod
    def is_valid(cls, path: Path|str) -> bool:
        ...
    def __bool__(self):
        return True

class BaseExtractor(ABC):
    SUPPORTED_DIR_TYPE: Optional[SupportedDirType] = None # see the rimworld extractor for an example
    SUPPORTED_FILES_TYPES: Sequence[str] = []  # List of supported file extensions (e.g., ['.json', '.xml'])
    additional_columns: Sequence[str] = []  # List of additional column names that the extractor may use in the TextUnit's other_attrs
    @abstractmethod
    def extract_file(self, path: str | Path) -> list[TextUnit]:
        ...
    @abstractmethod
    def apply_translations(self, path: str | Path, text_units: list[TextUnit], save_path: Optional[Path|str] = None, **kwargs):
        ...
    def extract_dir(self, path: str | Path, *args, **kwargs) -> list[TextUnit]:
        logger.warning(f"extract_dir is not implemented for {self.__class__.__name__}. Falling back to extract_file.")
        return self.extract_file(path, *args, **kwargs)
