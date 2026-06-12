import json
from pathlib import Path
from typing import Optional
from core.json_path import JsonPath
from core.text_unit import TextUnit
from utils import walk_json
from .schema import TRANSLATION_FIELDS, EVENT_TRANSLATION_CODES

class RPGMakerMVExtractor:
    SUPPORTED_FILES_TYPES = ['.json']
    def extract_file(self, path: Path|str) -> list[TextUnit]:
        path = Path(path)
        stem = path.stem
        if stem.startswith("Map"):
            return self._extract_map(path)
        if stem == "CommonEvents":
            return self._extract_events_file(path)
        return self._extract_db_file(path)
    
    def _extract_db_file(self, path: Path) -> list[TextUnit]:
        """Extracts text units from a database file (e.g., Actors.json, Items.json). """
        out: list[TextUnit] = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for i,item in enumerate(data):
            if not isinstance(item, dict):
                continue
            for field in TRANSLATION_FIELDS.get(path.stem, []):
                text = item.get(field, "")
                if isinstance(text, str) and text.strip():
                    out.append(TextUnit(
                        file=path.stem,
                        id=str(item.get("id", "")),
                        attribute=field,
                        original=text,
                        translation=text, # Initialize translation with original text for easier editing in the table
                        json_path=JsonPath.from_list([i, field])
                    ))
        return out
    def _extract_events_file(self, path: Path) -> list[TextUnit]:
        """Extracts text units from the CommonEvents.json file, which contains event data. """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self._extract_event_pages(path, data)
    
    def _extract_map(self, path: Path) -> list[TextUnit]:
        """Extracts text units from a map file, looking for event pages within the map data. """
        out: list[TextUnit] = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for i,event in enumerate(data.get("events", [])):
            if not isinstance(event, dict):
                continue
            out.extend(self._extract_event_pages(
                path, event.get("pages", []), 
                json_path = JsonPath.from_list(['events', i, 'pages'])
            ))
        return out

    def _extract_event_pages(self, path: Path, pages: list, json_path: Optional[JsonPath]=None) -> list[TextUnit]:
        """Extracts text units from event pages, looking for specific command codes that contain translatable text. 
        
        Example of event data structure:
        ```
        [ ...,
          {"id": 2, "list": [{"code": 401, "indent": 0, "parameters": ["Translatable Text"]}]            
        ]            
        ```
        """
        out: list[TextUnit] = []
        json_path = json_path or JsonPath.from_list([])
        for item in pages:
            if not isinstance(item, dict):
                continue
            for command in item.get("list", []):
                cmd_type = EVENT_TRANSLATION_CODES.get(command.get("code"))
                if not cmd_type:
                    continue
                for param, current_path, parent in walk_json(command.get("parameters", [])):
                    if isinstance(param, str) and param.strip():
                        out.append(TextUnit(
                            file=path.stem,
                            id=str(item.get("id", "")),
                            attribute=f"CMD:{cmd_type}",
                            original=param,
                            translation=param, # Initialize translation with original text for easier editing in the table
                            json_path=json_path + JsonPath.from_list(current_path)
                        ))
        return out
    
    def apply_translations(
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
            if text_unit.json_path and text_unit.translation != text_unit.original:
                apply_json_path(data, text_unit.json_path, text_unit.translation)
        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=kwargs.get("indent", 4))


def apply_json_path(data: dict, json_path: JsonPath, new_value: str):
    """Applies a new value to a JSON structure at the location specified by the JsonPath. """
    current = data
    for part in json_path.parts[:-1]:
        current = current[part]
    current[json_path.parts[-1]] = new_value
