"""
Extractor for Rimworld's XML language files.
https://rimworldwiki.com/wiki/Modding_Tutorials/Localization
"""
import logging
from pathlib import Path
from typing import Iterator, Optional, Literal, override
from pandas import DataFrame
from lxml import etree as ET

from .. import BaseExtractor, SupportedDirType
from .version import VERSION, FALLBACK_VERSION
from core.json_path import JsonPath
from core.text_unit import TextUnit
from core.translation.level import TranslationLevel

logger = logging.getLogger(__name__)

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

def rimworld_dir_iter(mod_dir:Path, subdir:Literal["Languages","Defs", "Textures"],version:str=VERSION, fallback_version = FALLBACK_VERSION)-> Iterator[Path]:
    """Get the list of specific subdir directories from a loadFolders.xml file."""
    load_folders_xml = mod_dir / "loadFolders.xml"
    # Case 1: loadFolders.xml does not exist:
    # should find the Languages folder at either root, version, or fallback_version.
    if not load_folders_xml.exists():
        if (mod_dir/version/subdir).exists():
            yield mod_dir/version/subdir
            return
        if (mod_dir/subdir).exists():
            yield mod_dir/subdir
            return
        elif (mod_dir/fallback_version/subdir).exists():
            yield mod_dir/fallback_version/subdir
            return
        logger.warning(f"loadFolders.xml not found in {load_folders_xml.parent}.")
        return
    
    # Case 2: loadFolders.xml exists
    tree = ET.parse(load_folders_xml)
    root = tree.getroot()
    version_elem = root.find(f"v{fallback_version}") if (tmp:=root.find(f"v{version}")) is None else tmp
    if version_elem is None:
        logger.warning(f"Version {version} not found in loadFolders.xml.")
        return
    for li in version_elem.findall("li"):
        if li.text is not None:
            if li.text =='/' and (mod_dir/subdir).exists():
                yield mod_dir/subdir
            elif (lang_dir:=(mod_dir/li.text/subdir)).exists():
                yield lang_dir

class RimworldModDirType(SupportedDirType):
    """A type that represents a valid Rimworld mod directory, which contains a `About/About.xml` file."""
    MSG_FORMAT = "Directory {path} is not a valid {self}. Expected an 'About/About.xml' file."
    def is_valid(self, path: Path|str) -> bool:
        path = Path(path)
        return (path/"About"/"About.xml").exists()

class RimWorldExtractor(BaseExtractor):
    SUPPORTED_DIR_TYPE = RimworldModDirType("RimworldMod")
    SUPPORTED_FILES_TYPES = ['.xml']
    @override
    def extract_file(self, path: Path|str) -> list[TextUnit]:
        path = Path(path)
        if path.suffix == ".xml":
            return self._extract_lang_file(path)
        elif path.suffix == ".txt":
            return self._extract_strings(path)
        elif path.is_dir():
            return self.extract_dir(path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    @override
    def extract_dir(self, path: Path|str, source_lang: str='en', target_lang: str='en', **kwargs) -> list[TextUnit]:
        path = Path(path)
        assert path.is_dir(), f"Path {path} is not a directory."
        if self.SUPPORTED_DIR_TYPE.is_valid(path): # Note: This is actually already checked in the session
            return self.extract_mod(path, source_lang=source_lang, target_lang=target_lang, **kwargs)
        elif path.name == "Definjected" or path.name == "Keyed":
            return self._extract_xml_folder(path, root_dir=path.name)
        elif path.name == "Strings":
            return self._extract_strings_folder(path)
        else:
            return self.extract_language_folder(path)
        
    def _extract_lang_file(self, path: Path|str, json_prefix:Optional[list]=None, root_dir:Optional[Path|str]=None) -> list[TextUnit]:
        """Extracts text units from a language XML file. """
        path = Path(path)
        root_dir = Path(root_dir) if root_dir is not None else path.parent
        json_prefix = json_prefix or []
        lang_data = load_xml_file(path)
        out: list[TextUnit] = []
        for key, text in lang_data.items():
            if not isinstance(key,(str, int)): # skip comments
                continue
            if isinstance(text, str) and text.strip():
                out.append(TextUnit(
                    file=path.relative_to(root_dir).as_posix(),
                    key=JsonPath(json_prefix + [key]),
                    original=text,
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
            file="Strings/" + path.name,
            key=JsonPath(json_prefix + [i]),
            original=line.strip(),
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

    def _extract_xml_folder(self, folder: Path|str, root_dir: Optional[Path|str] = None)-> list[TextUnit]:
        """Extract all XML files from a folder, and combine the result into a list of TextUnits. """
        folder = Path(folder)
        out: list[TextUnit] = []
        for file in folder.rglob("*.xml"):
            rel_dir = file.parent.relative_to(folder)
            json_prefix = list(rel_dir.parts) if rel_dir.parts != ('.',) else None
            out.extend(self._extract_lang_file(file, json_prefix=json_prefix, root_dir=root_dir))
        return out
    
    def _apply_xml_folder(self, folder: Path|str, text_units: list[TextUnit]|DataFrame, save_path: Optional[Path|str] = None, **kwargs):
        """Apply translations to all XML files in a folder, and save the results to a new folder. """
        folder = Path(folder)
        save_path = Path(save_path or folder)
        if isinstance(text_units, list):
            text_units_df = DataFrame(text_units)
        else:
            text_units_df = text_units
            
        for file in folder.rglob("*.xml"):
            rel_dir = file.parent.relative_to(folder)
            json_prefix = list(rel_dir.parts) if rel_dir.parts != ('.',) else None
            file_units = text_units_df[text_units_df['file'] == file.stem]
            self._apply_lang_file(file, file_units, save_path=save_path / rel_dir / file.name, json_prefix=json_prefix)

    def extract_language_folder(self, root: Path|str):
        """Extract all language files from a mod's Language folder. 
        
        {root}: {mod}/Language/{language}/ (e.g., MyMod/Language/English/)
          - Definjected/ : walk path and extract all XML files
          - Keyed/: list dir extract all XML files
          - Strings/: list dir extract all text files, split by linebreaks
        """
        root = Path(root)
        unit_list: list[TextUnit] = []
        if (path:=(root/"Strings")).exists():
            unit_list.extend(self._extract_strings_folder(path))
        if (path:=(root/"Definjected")).exists():
            unit_list.extend(self._extract_xml_folder(path, root_dir=root))
        if (path:=(root/"Keyed")).exists():
            unit_list.extend(self._extract_xml_folder(path, root_dir=root))
        # # if not unit_list:
        #     logger.warning(f"No supported language files found in {root}. Make sure the folder structure is correct (e.g., MyMod/Language/English/Definjected/*.xml).")
        return unit_list
    
    def extract_mod_languages(self, mod_dir: Path|str, version:str=VERSION, fallback_version = FALLBACK_VERSION, language: str='en') -> list[TextUnit]:
        """Extract all language files from a mod, 
        found by searching for `Languages` subfolders loaded in the mod's loadFolders.xml file.
        """
        
        from .languages import code2lang
        language = code2lang.get(language, language)  # Convert language code to name if possible
        if language not in code2lang.values():
            logger.warning(f"Language '{language}' not found in code2lang mapping. Using as-is.")
        
        unit_list: list[TextUnit] = []
        for lang_dir in rimworld_dir_iter(Path(mod_dir), "Languages", version=version, fallback_version=fallback_version):
            for subfolder in lang_dir.iterdir():
                if (subfolder.is_dir() and 
                    subfolder.name[:len(language)].lower() == language.lower()
                ):
                    unit_list.extend(self.extract_language_folder(subfolder))
        return unit_list
    
    def extract_mod_translatable(self, mod_dir: Path|str, version: str=VERSION, fallback_version: str=FALLBACK_VERSION) -> list[TextUnit]:
        """Extract translatable text from an XML file."""
        from .extract_translatable import extract_translatable
        mod_dir = Path(mod_dir)
        unit_list: list[TextUnit] = []
        for def_dir in rimworld_dir_iter(mod_dir, "Defs", version=version, fallback_version=fallback_version):
            for xml_file in def_dir.rglob('*.xml'):
                unit_list.extend(extract_translatable(xml_file, json_prefix=None, root_dir=mod_dir))
        return unit_list
    
    def extract_mod(self, mod_dir: Path|str, version: str=VERSION, fallback_version: str=FALLBACK_VERSION, source_lang: str='en', target_lang: str='en', **kwargs) -> list[TextUnit]:
        """Extract all translatable text and language files from a mod."""
        mod_dir = Path(mod_dir)
        unit_list: list[TextUnit] = []
        translatable_units = self.extract_mod_translatable(mod_dir, version=version, fallback_version=fallback_version)
        target_lang_units = self.extract_mod_languages(mod_dir, version=version, fallback_version=fallback_version, language=target_lang)
        source_lang_units = self.extract_mod_languages(mod_dir, version=version, fallback_version=fallback_version, language=source_lang)
        # Load order: target_lang_units > source_lang_units > translatable_units
        # Higher order prioritize over others if they have the same key
        unit_dict = {unit.key: unit for unit in translatable_units}
        for unit in source_lang_units:
            if unit.key in unit_dict:
                unit_dict[unit.key].translation = unit.translation # replace only the translation
            else:
                unit_dict[unit.key] = unit
        for unit in target_lang_units:
            if unit.key in unit_dict:
                unit_dict[unit.key].translation = unit.translation # replace only the translation
            else:
                unit_dict[unit.key] = unit
            unit_dict[unit.key].level = TranslationLevel.VERIFIED # mark as translated if target language is found
        return list(unit_dict.values())
    
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
    @override
    def apply_translations(
        self, file_path: Path|str, 
        text_units: list[TextUnit]|DataFrame, 
        save_path: Optional[Path|str] = None,
        target_lang: Optional[str] = None,
        **kwargs
    ):
        """Apply translations to a file or folder, and save the result to a new file or folder. """
        file_path = Path(file_path)
        if file_path.is_dir():
            if file_path.name == "Definjected" or file_path.name == "Keyed":
                self._apply_xml_folder(file_path, text_units, save_path=save_path, **kwargs)
            elif file_path.name == "Strings":
                self._apply_strings_folder(file_path, text_units, save_path=save_path, **kwargs)
            elif save_path is None:
                logger.info(f"(DEPRECATED) Applying translations to mod directory {file_path}.")
                self.apply_mod_translations(file_path, text_units, save_path=save_path, **kwargs)
            else:
                if target_lang is None:
                    logger.warning(f"Target language not specified. Using 'en' as default.")
                    target_lang = 'en'
                logger.info(f"Exporting translations to mod directory {save_path}.")
                self.export_mod_translations(file_path, save_path, text_units, target_lang, **kwargs)
        elif file_path.suffix == ".xml":
            self._apply_lang_file(file_path, text_units, save_path=save_path, **kwargs)
        elif file_path.suffix == ".txt":
            self._apply_strings_file(file_path, text_units, save_path=save_path, **kwargs)
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
    
    def export_mod_translations(self, 
        mod_root:Path|str, save_root: Path|str, text_units: list[TextUnit]|DataFrame, language:str,
        translation_mod_fields: Optional[dict] = None, about:bool=True,**kwargs
    ):
        """Export translations as a new mod.
        
        Args:
            mod_root (Path|str): The path to the original mod directory.
            save_root (Path|str): The path where the new mod will be saved.
            text_units (list[TextUnit]|DataFrame): The list of text units containing translations.
            language (str): The language of the translations.
            translation_mod_fields (Optional[dict]): A dictionary containing fields for the new mod's About.xml file, such as name, packageID, author, load_after, supported_versions, and description.
                - name (str): The name of the new mod. Default is "Translated Mod".
                - packageID (str): The package ID of the new mod. Default is "unknown.translated.mod".
                - author (str): The author of the new mod. Default is "Unknown".
                - load_after (list[str]): A list of mod IDs that this mod should be loaded after. Default is an empty list.
                - supported_versions (list[str]): A list of supported game versions. Default is ['1.6'].
                - description (str): A description of the new mod. Default is "This mod is generated by RimWorld Chinese Converter."
        """
        from .mod_builder import write_about_xml, load_about_xml, read_load_folders_xml
        from .languages import code2lang
        language = code2lang.get(language, language)  # Convert language code to name if possible
        assert language in code2lang.values(), f"Language '{language}' not found in code2lang mapping. Please provide a valid language name."
        mod_fields = {
            "name": "Unknown Mod (Translated)",
            "packageID": "unknown.mod.translated",
            "author": "Unknown",
            "load_after": [],
            "supported_versions": [VERSION],
            "description": ""
        }
        
        if isinstance(text_units, list):
            text_units = DataFrame(text_units)
        if (original_about := load_about_xml(Path(mod_root))) is not None:
            if name := original_about.findtext("name") :
                mod_fields['name'] = name+" (Translated)"
            if (load_after := original_about.find("loadAfter")) is not None:
                mod_fields['load_after'] = [li.text for li in load_after.findall("li") if li.text]
            if package_id := original_about.findtext("packageId"):
                mod_fields['packageID'] = package_id+""
                mod_fields['load_after'] += [package_id]
            mod_fields['author'] = original_about.findtext("author", default=mod_fields['author'])
            mod_fields['description'] = original_about.findtext("description", default=mod_fields['description'])
        mod_fields = mod_fields|(translation_mod_fields or {})

        # Categorize the text units by their file type and file directory.
        definjected_reldirs = text_units.file.str.extract("(.*/)*Defs/")[0]
        unique_reldirs = definjected_reldirs.dropna().unique()
        is_definjected = definjected_reldirs.notna()
        is_strings = text_units.file.str.match(r".*\.txt")
        is_keyed = ~is_definjected & ~is_strings
        
        save_root = Path(save_root)
        if about:
            write_about_xml(save_root, **mod_fields)
        
        for reldir in unique_reldirs:
            self._export_xml_translations(
                save_root/reldir/"Languages"/language, 
                text_units[is_definjected & (definjected_reldirs == reldir)]
            )
        
        # TODO: Also export Keyed and Strings following the original mod's structure if they exist.
        self._export_xml_translations(save_root/"Languages"/language, text_units[is_keyed])
        self._export_str_translations(save_root/"Languages"/language, text_units[is_strings])
        
        # Build a new loadFolders.xml modified from the original mod's
        if ( 
            (tree := read_load_folders_xml(Path(mod_root))) is not None and
            (version_elem:= tree.find(f"v{VERSION}")) is not None # keep only the latest VERSION
        ):
            for li in version_elem.findall("li"):
                if li.text is None or li.text == "/":
                    continue
                # check if the folder is in the definjected_reldirs, if not, remove it from the tree
                if li.text not in unique_reldirs and (li.text+'/') not in unique_reldirs:
                    version_elem.remove(li)
            # write the modified loadFolders.xml to the new mod
            root = ET.Element("loadFolders")
            new_tree = ET.ElementTree(root)
            root.append(version_elem)
            save_load_folders_path = save_root/"loadFolders.xml"
            new_tree.write(save_load_folders_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
        
    def _export_xml_translations(self, save_root: Path, text_units: DataFrame):
        """Export translations to the Definjected folder of a mod."""
        # definjected_path = mod_root/"Languages"/"Definjected"
        for file in text_units['file'].unique():
            if not file.endswith(".xml"):
                continue
            file_units = text_units[text_units['file'] == file]
            # Build a ET Tree for the file
            root = ET.Element("LanguageData")
            file_name = Path(file).name
            deftype = None # prevent deftype being unbound
            for unit in file_units.itertuples():
                keyparts = unit.key.parts
                translation_key = keyparts[-1]
                if len(keyparts) == 2:
                    deftype = keyparts[0]
                elif len(keyparts) ==1:
                    deftype = None
                else:
                    deftype = None
                    logger.error(f"Unexpected key format for unit {unit}: {unit.key}. Expected 1 or 2 parts, got {len(keyparts)}.")
                # Create the XML element for the translation
                entry = ET.SubElement(root, translation_key)
                entry.text = unit.translation
            if deftype is not None:
                save_path = save_root/"Definjected"/deftype/file_name
            else:
                save_path = save_root/"Keyed"/file_name
            save_path.parent.mkdir(parents=True, exist_ok=True)
            tree = ET.ElementTree(root)
            tree.write(save_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
            
    def _export_str_translations(self, save_root: Path, text_units: DataFrame,):
        """Export translations to the Strings folder of a mod."""
        for file in text_units['file'].unique():
            if not file.endswith(".txt"):
                continue
            file_units = text_units[text_units['file'] == file]
            # Build the lines for the file
            lines = []
            for unit in file_units.itertuples():
                lines.append(unit.translation)
            save_path = save_root/"Strings"/Path(file).name
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text("\n".join(lines), encoding="utf-8")