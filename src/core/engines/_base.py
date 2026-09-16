import logging
from pathlib import Path
from typing import Optional, Sequence
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
