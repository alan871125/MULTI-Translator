from pathlib import Path
from typing import ClassVar, Protocol, Sequence

from core.text_unit import TextUnit

class BaseExtractor(Protocol):
    SUPPORTED_FILES_TYPES: ClassVar[Sequence[str]]  # List of supported file extensions (e.g., ['.json', '.xml'])

    def extract_file(self, file_path: str | Path) -> list[TextUnit]:
        ...
