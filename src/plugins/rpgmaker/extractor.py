import re
import json
import logging
from pathlib import Path
from typing import Callable, Optional, override
from concurrent.futures import ThreadPoolExecutor

from core.json_path import JsonPath
from core.text_unit import TextUnit
from core.json_utils import walk_json

from .schema import TRANSLATION_FIELDS, EVENT_TRANSLATION_CODES, PLUGIN_HANDLERS
from ..simple_json import apply_json_path
from .. import registered_extractor, SubDirCheckType, BaseExtractor
logger = logging.getLogger(__name__)


def _json_dump_worker(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

ENCLOSED_STRING_PATTERN = re.compile(r"^`.*`$|^\".*\"$|^'.*'$|^「.*」$")
class CmdExtractor:
    def __init__(self, path: Path, json_prefix: Optional[tuple]=None):
        self.path = path
        self.json_prefix = json_prefix or ()
        self._handlers: dict[int, Callable[[list, tuple], list[TextUnit]]] = {
            101: self._extract_101,
            122: self._extract_122,
            357: self._extract_357,
        }
        
    def extract_cmds(self, cmds: list[dict]) -> list[TextUnit]:
        cmd_data = []
        for j, command in enumerate(cmds):
            if not (
                (cmd_code:=command.get("code")) and
                (cmd_type:=EVENT_TRANSLATION_CODES.get(cmd_code)) and
                (params := command.get("parameters"))
            ):
                continue
            cmd_data.extend(self.extract(cmd_code, params, (self.path.stem, *self.json_prefix, j, 'parameters')))
        return cmd_data

    def extract(self, cmd_code:int, params: list, json_prefix: tuple=()) -> list[TextUnit]:
        handler = self._handlers.get(cmd_code, self._extract)
        return handler(params, json_prefix)
    
    def _extract(self, params:list, json_prefix: tuple)  -> list[TextUnit]:
        out = []
        for param, current_path, parent in walk_json(params):
            if isinstance(param, str) and param.strip():
                json_suffix = (*json_prefix, *current_path)
                out.append(TextUnit(
                    file=self.path.stem,
                    key=JsonPath._from_parts(json_suffix),
                    original=param
                ))
        return out
    
    def _extract_101(self, params: list, json_prefix: tuple)  -> list[TextUnit]:
        """Extract Code 101 (ShowText) command parameters"""
        if params[4].strip():
            return [TextUnit(
                file=self.path.stem,
                key=JsonPath._from_parts((*json_prefix, 4)),
                original=params[4]
            )]
        return []
    
    def _extract_122(self, params: list, json_prefix: tuple)  -> list[TextUnit]: #ControlVariables
        """Extract Code 122 (ControlVariables) command parameters
        
        Identifying translatable text in ControlVariables command is quite tricky. I assume:
        1. Single variable assignment (start_id == end_id)
        2. The operand is a string (operand_type == 4)
        3. The string is enclosed in backticks (e.g., `Translatable Text`) or quotes or Chinese quotes.
        
        **Note: This is a heuristic and may not cover all cases. Further refinement may be needed based on actual game data.**
        """
        match params:
            case [start_id, end_id, 0, 4, str() as operand_text]:
                if not operand_text or operand_text[0] == '$': # Skip variable references like $gameVariables.value(1)
                    return []
                elif start_id==end_id and ENCLOSED_STRING_PATTERN.match(operand_text):
                    return [TextUnit(
                        file=self.path.stem,
                        key=JsonPath._from_parts((*json_prefix, 4)),
                        original=operand_text
                    )]
                else:
                    return []
            case _:
                return []

    def _extract_357(self, params: list, json_prefix: tuple)  -> list[TextUnit]: #PluginCommand
        """Extract Code 357 (PluginCommand) command parameters"""
        plugin, method, _, method_kwargs,*_ = params
        if (translatable_path := PLUGIN_HANDLERS.get((plugin, method))) is not None:
            v = translatable_path.fetch(method_kwargs)
            return [TextUnit(
                file=self.path.stem,
                key=JsonPath._from_parts((*json_prefix, 3,*translatable_path._parts)),
                original=v
            )]
        return []

@registered_extractor(name='RPG Maker MV')
class RPGMakerMVExtractor(BaseExtractor):
    DATA_SUBDIR = "www/data"
    SUPPORTED_DIR_TYPE = SubDirCheckType(DATA_SUBDIR)
    SUPPORTED_FILES_TYPES = ['.json']
    additional_columns = ['attribute']
    @override
    def extract_file(self, path: Path|str) -> list[TextUnit]:
        path = Path(path)
        stem = path.stem
        if stem.startswith("Map") and stem[3:].isdigit(): # prevent matching files like "MapInfo.json" or "MapVoice.json"
            return self._extract_map(path)
        if stem == "CommonEvents":
            return self._extract_events_file(path)
        return self._extract_db_file(path)
    
    @override
    def extract_dir(self, dir_path: Path|str, source_lang: Optional[str]=None, target_lang: Optional[str]=None) -> list[TextUnit]:
        """Extracts text units from all supported files in a directory."""
        dir_path = Path(dir_path)
        out: list[TextUnit] = []
        if not (self.SUPPORTED_DIR_TYPE and self.SUPPORTED_DIR_TYPE.is_valid(dir_path)):
            raise ValueError(f"Directory {dir_path} does not appear to be a valid RPG Maker MV project (missing {self.DATA_SUBDIR} subdirectory).")
        # for file_path in (dir_path/self.DATA_SUBDIR).iterdir():
        #     if file_path.suffix.lower() in self.SUPPORTED_FILES_TYPES:
        #         out.extend(self.extract_file(file_path))
        with ThreadPoolExecutor() as executor:
            futures = []
            for file_path in (dir_path/self.DATA_SUBDIR).iterdir():
                if file_path.suffix.lower() in self.SUPPORTED_FILES_TYPES:
                    futures.append(executor.submit(self.extract_file, file_path))
            for future in futures:
                out.extend(future.result())
        return out
    
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
                        key=JsonPath([path.stem, i, field]),
                        original=text,
                        other_attrs={"attribute":field,}
                    ))
        return out
    
    @staticmethod
    def _extract_events_file(path: Path) -> list[TextUnit]:
        """Extracts text units from the CommonEvents.json file, which contains event data. """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RPGMakerMVExtractor._extract_event_pages(path, data)
    
    @staticmethod
    def _extract_map(path: Path) -> list[TextUnit]:
        """Extracts text units from a map file, looking for event pages within the map data. """
        out: list[TextUnit] = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if display_name := data.get("displayName"):
            out.append(TextUnit(
                file=path.stem,
                key=JsonPath([path.stem, "displayName"]),
                original=display_name,
            ))
        
        for i,event in enumerate(data.get("events", [])):
            if not isinstance(event, dict):
                continue
            out.extend(RPGMakerMVExtractor._extract_event_pages(
                path, event.get("pages", []), 
                json_prefix = ('events', i, 'pages')
            ))
        return out
    
    @staticmethod
    def _extract_event_pages(path: Path, pages: list, json_prefix: Optional[tuple]=None) -> list[TextUnit]:
        """Extracts text units from event pages, looking for specific command codes that contain translatable text. 
        
        Example of event data structure:
        ```
        [ ...,
          {"id": 2, "list": [{"code": 401, "indent": 0, "parameters": ["Translatable Text"]}]
        ]            
        ```
        """
        out: list[TextUnit] = []
        json_prefix = json_prefix or ()
        for i, item in enumerate(pages):    
            if not isinstance(item, dict):
                continue
            elif (command_list := item.get("list")):
                cmd_extractor = CmdExtractor(path, json_prefix=(*json_prefix, i, 'list'))
                out.extend(cmd_extractor.extract_cmds(command_list))
        return out
    
    @override
    def apply_translations(self, file_path: str | Path, text_units: list[TextUnit], save_path: Optional[Path|str] = None, target_lang:Optional[str] = None, **kwargs)->Optional[bool]:
        file_path = Path(file_path)/self.DATA_SUBDIR
        if save_path is None:
            save_path = file_path  # Overwrite the original file if no save path is provided
            logger.warning(f"No save_path provided. Overwriting the original file: {file_path}")
        else:
            save_path = Path(save_path)
        # TODO: Implement backup logic before overwriting the original file, if save_path is None.
        if file_path.is_dir():
            data = {}
            for p in file_path.glob("*.json"):
                with open(p, "r", encoding="utf-8") as f:
                    data[p.stem] = json.load(f)
            for unit in text_units:
                apply_json_path(data, unit.key, unit.translation)
            with ThreadPoolExecutor() as executor:
                futures = []
                for k, v in data.items():
                    save_file_path = (save_path/k).with_suffix(".json")
                    futures.append(executor.submit(_json_dump_worker, save_file_path, v))
                for future in futures:
                    future.result()  # Wait for all write operations to complete
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for text_unit in text_units:
                if text_unit.key and text_unit.translation != text_unit.original:
                    apply_json_path(data, text_unit.key, text_unit.translation)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=kwargs.get("indent", 4))

@registered_extractor(name='RPG Maker MZ')
class RPGMakerMZExtractor(RPGMakerMVExtractor):
    DATA_SUBDIR = "data"
    SUPPORTED_DIR_TYPE = SubDirCheckType(DATA_SUBDIR)


    
