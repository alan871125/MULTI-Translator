from pathlib import Path
from typing import ClassVar, Optional, Protocol, Sequence

from core.text_unit import TextUnit

class BaseExtractor(Protocol):
    SUPPORTED_FILES_TYPES: ClassVar[Sequence[str]]  # List of supported file extensions (e.g., ['.json', '.xml'])

    def extract_file(self, file_path: str | Path) -> list[TextUnit]:
        ...
    def apply_translations(self, file_path: str | Path, text_units: list[TextUnit], save_path: Optional[Path|str] = None, **kwargs):
        ...