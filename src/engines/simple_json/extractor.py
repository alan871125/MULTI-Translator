import json
from pathlib import Path
from core.text_unit import TextUnit
from utils import walk_json

class SimpleJsonExtractor:
    SUPPORTED_FILES_TYPES = ['.json']
    def extract_file(self, path: Path|str) -> list[TextUnit]:
        path = Path(path)
        stem = path.stem
        out: list[TextUnit] = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for value, json_path, _ in walk_json(data):
            if isinstance(value, str) and value.strip():
                out.append(TextUnit(
                    file=path.stem,
                    id="-",  # No specific ID for simple JSON, using a placeholder
                    attribute="-",  # No specific attribute, using a placeholder
                    original=value,
                    translation=value, # Initialize translation with original text for easier editing in the table
                    json_path=json_path
                ))
        return out