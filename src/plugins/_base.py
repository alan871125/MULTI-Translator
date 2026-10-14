import logging
from pathlib import Path
from typing import Optional, Sequence
from abc import ABC, abstractmethod
from core.text_unit import TextUnit
logger = logging.getLogger(__name__)

class SupportedDirType(ABC):
    MSG_FORMAT = "Directory {path} is not a valid {self}."
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
    @abstractmethod
    def is_valid(self, path: Path|str) -> bool:
        ...
    def check(self, path: Path|str) -> bool:
        if not self.is_valid(path):
            logger.error(self.MSG_FORMAT.format(path=path, self=str(self)))
            return False
        return True

    def __bool__(self) -> bool:
        return True
    def __str__(self):
        return self.name
class SupportedDirInvalidType(SupportedDirType):
    """A type that represents no supported directory type."""
    MSG_FORMAT = "The current engine does not support directory extraction."
    def is_valid(self, path: Path|str) -> bool:
        return False
    def __bool__(self):
        return False
class SubDirCheckType(SupportedDirType):
    """A simple implementation of SupportedDirType that checks if a directory exists."""
    MSG_FORMAT = "Directory {path} does not contain the required subdirectory '{self}'."
    def __init__(self, *subdirs: str, name: Optional[str] = None):
        super().__init__(name)
        self.subdirs = subdirs
    def is_valid(self, path: Path|str) -> bool:
        return all((Path(path)/s).exists() for s in self.subdirs)
    def __str__(self):
        return f"{self.name}(requires subdirs: {', '.join(self.subdirs)})"

class UnsupportedDirectoryError(Exception):
    """Raised when a directory is not of the expected type."""
    ...

class BaseExtractor(ABC):
    SUPPORTED_DIR_TYPE: SupportedDirType = SupportedDirInvalidType() # see the rimworld extractor for an example
    SUPPORTED_FILES_TYPES: Sequence[str] = []  # List of supported file extensions (e.g., ['.json', '.xml'])
    additional_columns: Sequence[str] = []  # List of additional column names that the extractor may use in the TextUnit's other_attrs
    @abstractmethod
    def extract_file(self, path: str | Path) -> list[TextUnit]:
        """
        Extracts text units from a single file and returns them as a list of TextUnit objects
        """
        ...
    @abstractmethod
    def apply_translations(self, file_path: str | Path, text_units: list[TextUnit], save_path: Optional[Path|str] = None, target_lang:Optional[str] = None, **kwargs)->Optional[bool]:
        """
        Apply translations from a list of TextUnit objects back into the original file, saving the result to a new file if save_path is provided. 
        
        Arguments:
            file_path (str | Path): The path to the original file.
            text_units (list[TextUnit]): A list of TextUnit objects containing the translations to be applied.
            save_path (Optional[Path|str]): The path where the modified file should be saved. If None, the original file will be overwritten.
            target_lang (Optional[str]): The language into which the text should be translated.
            **kwargs: Additional keyword arguments that may be used by specific extractors for custom behavior.
        Returns:
            Optional[bool]: True if the operation was successful, False if it failed, or None if the operation is not applicable for the specific extractor.
        
        """
        ...
    def extract_dir(self, path: str | Path, *args, **kwargs) -> list[TextUnit]:
        """
        Extracts text units from all supported files in a directory and returns them as a list of TextUnit objects.
        
        Behavior of this method is dependent on the specific extractor implementation.
        For example, some game extractors extract a directory as a whole (e.g., a mod folder).
        """
        
        logger.warning(f"extract_dir is not implemented for {self.__class__.__name__}. Falling back to extract_file.")
        return self.extract_file(path, *args, **kwargs)
