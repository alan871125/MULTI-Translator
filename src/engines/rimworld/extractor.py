"""
Extractor for Rimworld's XML language files.
https://rimworldwiki.com/wiki/Modding_Tutorials/Localization
"""
import json
from pathlib import Path
from typing import Optional, overload
from pandas import DataFrame
from core.json_path import JsonPath
from core.text_unit import TextUnit
from lxml import etree as ET


def load_xml_file(path: Path|str) -> dict:
    """Loads an XML file and returns a dictionary of key-value pairs. """
    with open(path, "rb") as f:
        xml_string = f.read()
    root = ET.fromstring(xml_string)
    result = {c.tag: c.text for c in root}
    return result

def parse_xml_to_dict(xml_string):
    root = ET.fromstring(xml_string)
    result = {}
    for child in root:
        result[child.tag] = child.text
    return result

class RimWorldExtractor():
    SUPPORTED_FILES_TYPES = ['.xml']
    def extract_file(self, path: Path|str) -> list[TextUnit]:
        path = Path(path)
        if path.suffix == ".xml":
            return self._extract_lang_file(path)
        elif path.suffix == ".txt":
            return self._extract_strings(path)
        elif path.is_dir():
            if path.name == "Definjected" or path.name == "Keyed":
                return self._extract_xml_folder(path)
            elif path.name == "Strings":
                return self._extract_strings_folder(path)
            else:
                return self.extract_mod_languages(path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    
    def _extract_lang_file(self, path: Path|str, json_prefix:Optional[list]=None) -> list[TextUnit]:
        """Extracts text units from a language XML file. """
        path = Path(path)
        json_prefix = json_prefix or []
        lang_data = load_xml_file(path)
        out: list[TextUnit] = []
        for key, text in lang_data.items():
            if not isinstance(key,(str, int)): # skip comments
                continue
            if isinstance(text, str) and text.strip():
                out.append(TextUnit(
                    file=path.stem,
                    key=JsonPath(json_prefix + [key]),
                    original=text,
                    translation=text, # Initialize translation with original text for easier editing in the table
                ))
        return out
    
    def _apply_lang_file(self, path: Path|str, text_units: list[TextUnit]|DataFrame, save_path: Optional[Path|str] = None, **kwargs):
        """Apply translations to a language XML file, and save the result to a new file. """
        tree = ET.parse(path)
        root = tree.getroot()
        if isinstance(text_units, list):
            text_units = DataFrame(text_units)
        related_units = text_units[text_units['file'] == Path(path).stem]
        
        for unit in related_units.iloc:
            key = unit.key.parts[-1]
            translation = unit.translation
            if (element := root.find(key)) is not None:
                element.text = translation

        save_path = Path(save_path or path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(save_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
        
    def _extract_strings(self, path: Path|str, json_prefix:Optional[list]=None) -> list[TextUnit]:
        """Extracts text units from a strings file, strings splited by linebreaks. """
        # TODO: Move this to LineBreakedTextExtractor
        path = Path(path)
        json_prefix = json_prefix or []
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out = [TextUnit(
            file=path.stem,
            key=JsonPath(json_prefix + [i]),
            original=line.strip(),
            translation=line.strip(), # Initialize translation with original text for easier editing in the table
        ) for i, line in enumerate(lines) if line.strip()]
        return out
    def _extract_strings_folder(self, folder: Path|str):
        """Extracts text units from all strings files in a folder. """
        folder = Path(folder)
        out: list[TextUnit] = []
        for file in folder.rglob("*.txt"):
            rel_dir = file.parent.relative_to(folder)
            json_prefix = list(rel_dir.parts) if rel_dir.parts != ('.',) else None
            out.extend(self._extract_strings(file, json_prefix=json_prefix))
        return out
    
    def _apply_strings_file(self, path: Path|str, text_units: list[TextUnit]|DataFrame, save_path: Optional[Path|str] = None, **kwargs):
        """Apply translations to a strings file, and save the result to a new file. """
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if isinstance(text_units, list):
            text_units = DataFrame(text_units)
        related_units = text_units[text_units['file'] == Path(path).stem]
        for unit in related_units.iloc:
            line_idx:int = int(unit.key.parts[-1])
            lines[line_idx] = unit.translation + "\n"
            
        save_path = Path(save_path or path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("".join(lines), encoding="utf-8")
    
    
    def _apply_strings_folder(self, folder: Path|str, text_units: list[TextUnit]|DataFrame, save_path: Optional[Path|str] = None, **kwargs):
        """Apply translations to all strings files in a folder, and save the results to a new folder. """
        folder = Path(folder)
        save_path = Path(save_path or folder)
        if isinstance(text_units, list):
            text_units = DataFrame(text_units)
        for file in folder.rglob("*.txt"):
            rel_dir = file.parent.relative_to(folder)
            json_prefix = list(rel_dir.parts) if rel_dir.parts != ('.',) else None
            file_units = text_units[text_units['file'] == file.stem]
            self._apply_strings_file(file, file_units, save_path=save_path / rel_dir / file.name, json_prefix=json_prefix)

    def _extract_xml_folder(self, folder: Path|str):
        """Extract all XML files from a folder, and combine the result into a list of TextUnits. """
        folder = Path(folder)
        out: list[TextUnit] = []
        for file in folder.rglob("*.xml"):
            rel_dir = file.parent.relative_to(folder)
            json_prefix = list(rel_dir.parts) if rel_dir.parts != ('.',) else None
            out.extend(self._extract_lang_file(file, json_prefix=json_prefix))
        return out
    
    def _apply_xml_folder(self, folder: Path|str, text_units: list[TextUnit]|DataFrame, save_path: Optional[Path|str] = None, **kwargs):
        """Apply translations to all XML files in a folder, and save the results to a new folder. """
        folder = Path(folder)
        save_path = Path(save_path or folder)
        if isinstance(text_units, list):
            text_units = DataFrame(text_units)
            
        for file in folder.rglob("*.xml"):
            rel_dir = file.parent.relative_to(folder)
            json_prefix = list(rel_dir.parts) if rel_dir.parts != ('.',) else None
            file_units = text_units[text_units['file'] == file.stem]
            self._apply_lang_file(file, file_units, save_path=save_path / rel_dir / file.name, json_prefix=json_prefix)

    def extract_mod_languages(self, root: Path|str):
        """Extract all language files from a mod's Language folder. 
        
        {root}: {mod}/Language/{language}/ (e.g., MyMod/Language/English/)
          - Definjected/ : walk path and extract all XML files
          - Keyed/: list dir extract all XML files
          - Strings/: list dir extract all text files, split by linebreaks
        """
        root = Path(root)
        subfolders = {
            'Definjected': self._extract_xml_folder,
            'Keyed': self._extract_xml_folder,
            'Strings': self._extract_strings_folder,
        }
        unit_list: list[TextUnit] = []
        for subfolder, extractor in subfolders.items():
            path = root / subfolder
            if path.exists():
                unit_list.extend(extractor(path))
        # if not unit_list:
        #     logger.warning(f"No supported language files found in {root}. Make sure the folder structure is correct (e.g., MyMod/Language/English/Definjected/*.xml).")
        return unit_list
    
    def apply_mod_translations(self, language_path: Path|str, text_units: list[TextUnit]|DataFrame, save_path: Optional[Path|str] = None, **kwargs):
        """Apply translations to a mod's language files, and save the results to a new folder. """
        language_path = Path(language_path)
        save_path = Path(save_path or language_path)
        subfolders = {
            'Definjected': self._apply_xml_folder,
            'Keyed': self._apply_xml_folder,
            'Strings': self._apply_strings_folder,
        }
        for subfolder, applier in subfolders.items():
            path = language_path / subfolder
            if path.exists():
                applier(path, text_units, save_path=save_path / subfolder, **kwargs)
                
    def apply_translations(
        self, file_path: Path|str, 
        text_units: list[TextUnit]|DataFrame, 
        save_path: Optional[Path|str] = None,
        **kwargs
    ):
        """Apply translations to a file or folder, and save the result to a new file or folder. """
        file_path = Path(file_path)
        if file_path.is_dir():
            if file_path.name == "Definjected" or file_path.name == "Keyed":
                self._apply_xml_folder(file_path, text_units, save_path=save_path, **kwargs)
            elif file_path.name == "Strings":
                self._apply_strings_folder(file_path, text_units, save_path=save_path, **kwargs)
            else:
                self.apply_mod_translations(file_path, text_units, save_path=save_path, **kwargs)
        elif file_path.suffix == ".xml":
            self._apply_lang_file(file_path, text_units, save_path=save_path, **kwargs)
        elif file_path.suffix == ".txt":
            self._apply_strings_file(file_path, text_units, save_path=save_path, **kwargs)
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
    
    
