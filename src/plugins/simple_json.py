import json
from pathlib import Path
from typing import Optional
from ._base import BaseExtractor
from ._registry import registered_extractor
from core.json_path import JsonPath
from core.text_unit import TextUnit
from core.json_utils import walk_json

@registered_extractor(name='Simple JSON')
class SimpleJsonExtractor(BaseExtractor):
    SUPPORTED_FILES_TYPES = ['.json']
    key = 'json_path'
    columns = ['file','key','original','translation']
    def extract_file(self, path: Path|str) -> list[TextUnit]:
        path = Path(path)
        out: list[TextUnit] = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for value, json_path, _ in walk_json(data):
            if isinstance(value, str) and value.strip():
                out.append(TextUnit(
                    file=path.stem,
                    key=JsonPath(json_path),
                    original=value,
                ))
        return out
    
    def apply_translations( # type: ignore (ignores missing target_lang argument)
        self, file_path: Path|str, 
        text_units: list[TextUnit], 
        save_path: Optional[Path|str] = None,
        **kwargs
    ): 
        """Applies translations from a list of TextUnit objects back into the JSON file, saving the result to a new file if save_path is provided. """
        file_path = Path(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for text_unit in text_units:
            if text_unit.key and text_unit.translation != text_unit.original:
                apply_json_path(data, text_unit.key, text_unit.translation)
        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=kwargs.get("indent", 4))

def apply_json_path(data: dict, json_path: JsonPath, new_value: str):
    """Applies a new value to a JSON structure at the location specified by the JsonPath. """
    current = data
    for part in json_path.parts[:-1]:
        current = current[part]
    current[json_path.parts[-1]] = new_value