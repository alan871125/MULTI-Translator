import re
import logging
from pathlib import Path
from typing import Optional, Literal, TypeGuard, override, get_args
from concurrent.futures import ThreadPoolExecutor, as_completed
from pandas import DataFrame

from core.json_path import JsonPath
from core.text_unit import TextUnit
from ._base import BaseExtractor, SupportedDirType, UnsupportedDirectoryError

logger = logging.getLogger(__name__)
name = 'Crusader Kings III'
AvailableLanguage = Literal[
    'english', 'french', 'german', 'korean', 'polish', 'russian', 'simp_chinese', 'spanish', 
]
code2lang = { # google's language codes to paradox localization language names
    'en': 'english',
    'fr': 'french',
    'fr-CA': 'french',
    'de': 'german',
    'ko': 'korean',
    'pl': 'polish',
    'ru': 'russian',
    'zh-CN': 'simp_chinese',
    'zh-TW': 'simp_chinese',  # Treat traditional Chinese as simplified for CK3
    'es': 'spanish',
}

def is_available_language(lang: str) -> TypeGuard[AvailableLanguage]:
    return lang in get_args(AvailableLanguage)

def parse_yml(path: str | Path) -> dict[str, str]:
    """
    Parses a Paradox localization YAML file into a dictionary:
    Checks the following formats:
    - file_name: .*l_<language>.yml
    - file_content: l_<language>:...
    - file_name_language == file_content_language
    """
    
    path = Path(path)
    # get the language from the file name, which should be in the format l_<language>.yml
    if (m := _YML_LANG_NAME_REGEX.search(str(path))):
        language = m.group(1)
    else:
        language = None
        logging.warning("language not found in the file name, the game may not be able to recognize the localization file. The file name should be in the format l_<language>.yml")
    parsed_data = parse_yml_txt(path.read_text(encoding='utf-8-sig'))
    _language = next(iter(parsed_data.keys()), None)
    if _language is None:
        logging.error(f"No language found in the file content of {path}.")
        return {}
    elif _language is not None and _language != language:
        logging.error(f"Language in the file name ({language}) does not match the language in the file content ({_language}). The game may not be able to recognize the localization file.")
    return parsed_data[_language]

def parse_yml_txt(txt:str)->dict[str, dict[str, str]]:
    """
    Parses Paradox localization format into a nested dictionary:
    { "l_english": { "KEY": "Value text" } }
    
    Note that this parser does not handle more complex YAML features like multiple indent levels.
    """
    result = {}
    current_lang = None
    
    # Regex pattern breakdown:
    # ^\s*             : Optional leading whitespace
    # ([\w\.-]+)       : Group 1 -> Localization Key (e.g. MY_KEY_1)
    # (?::\d+)?        : Optional versioning/index number (e.g. :0 or :1)
    # \s+              : Whitespace before value
    # "(.*)"           : Group 2 -> Double-quoted value string
    # (?:\s*#.*)?$     : Optional trailing comments starting with #

    for line in txt.splitlines():
        # Remove trailing carriage returns and whitespace
        line = line.rstrip()
        
        # Skip blank lines or comment-only lines
        if not line or line.strip().startswith('#'):
            continue
        if not result and (
            (m:= _LANG_REGEX.search(line)) is not None and
            (current_lang := m.group("lang")) is not None
        ):
            result[current_lang] = {}
            continue
            
        # Match Key-Value pairs
        match = _KV_PATTERN.match(line)
        if match and current_lang:
            key, value = match.groups()
            # Unescape explicit escaped quotes inside strings if present
            value = value.replace(r'\"', '"')
            result[current_lang][key] = value

    return result
    
def write_yaml(language:AvailableLanguage, data: dict, file_path: Path):
    """
    Writes a nested dictionary to a Paradox localization YAML file.
    """
    assert file_path.as_posix().endswith(f"l_{language}.yml"), f"File name must end with l_{language}.yml"
    with open(file_path, 'w', encoding='utf-8-sig') as f:
        f.write(f"l_{language}:\n")
        for key, value in data.items():
            # Escape quotes in the value
            escaped_value = value.replace('"', r'\"')
            # the version number is not needed, so we can just write the key without it
            f.write(f'  {key}: "{escaped_value}"\n')

class CK3ModDirType(SupportedDirType):
    """A type that represents a valid CK3 mod directory, which contains a `About/About.xml` file."""
    MSG_FORMAT = "Directory {path} is not a valid CK3 mod directory. Expected a 'descriptor.mod' file and a 'localization' folder."
    def is_valid(self, path: Path|str) -> bool:
        path = Path(path)
        return (path/"descriptor.mod").exists() and (path/"localization").is_dir()

_LANG_PATTERN = '|'.join(get_args(AvailableLanguage))
_LANG_REGEX = re.compile(rf"l_(?P<lang>{_LANG_PATTERN})[\.yml$|:]")
_LOC_REGEX = re.compile(rf"localization/(?P<lang>{_LANG_PATTERN})/(?P<subdir>([^\"/]+/)*)?(?P<file_prefix>[^/]*_)?l_(?P=lang)\.yml$")
_FILE_REGEX = re.compile(rf"(?P<file_prefix>[^/]*_)?l_(?P<lang>{_LANG_PATTERN})\.yml$")
_YML_LANG_NAME_REGEX = re.compile(r'(?<![a-z])l_([a-z_]+)\.yml$')
_KV_PATTERN = re.compile(r'^\s*([\w\.-]+)(?::\d*)?\s+"(.*)"(?:\s*#.*)?$')

def delocalized_path(path: str | Path) -> str:
    """
    Converts a localization file path to a format string used as a unified key between source and target languages.
    
    Arguments:
        path (str | Path): The path to the localization file.
    Returns: 
        str: A format string representing the delocalized path, where the language part is replaced with `{lang}`.
            Three possible return cases:
            - Valid localization path: localization/<language>/<subdir>/<file>_l_<language>.yml
            - Invalid localization path but valid file name: <file>_l_<language>.yml
            - Invalid localization path and invalid file name: <file>.yml
    """
    path = Path(path)
    if m := _LOC_REGEX.search(path.as_posix()):
        subdir = m.group("subdir") or ""
        file_prefix = m.group("file_prefix") or ""
        return f"localization/{{lang}}/{subdir}{file_prefix}l_{{lang}}.yml"
    elif m := _FILE_REGEX.search(path.name):
        logger.warning(f"File {path} is not in a localization subdirectory. Expected 'localization/<language>/' subfolder.")
        file_prefix = m.group("file_prefix") or ""
        return f"{file_prefix}l_{{lang}}.yml"
    return path.name
    

def merge_units(source_units: dict[str, TextUnit], target_units: dict[str, TextUnit]) -> list[TextUnit]:
    keys = source_units.keys() | target_units.keys()
    merged = []
    for key in keys:
        source_unit = source_units.get(key)
        target_unit = target_units.get(key)
        if source_unit and target_unit:
            merged.append(TextUnit(source_unit.file, source_unit.key, source_unit.original, target_unit.translation))
        elif source_unit:
            merged.append(source_unit)
        elif target_unit:
            merged.append(target_unit)
    return merged

class Extractor(BaseExtractor):
    SUPPORTED_DIR_TYPE = CK3ModDirType('CK3 Mod Directory')
    SUPPORTED_FILES_TYPES = [".yml"]

    @staticmethod
    def _extract_file(path: str | Path, delocalize_path = True) -> dict[str, TextUnit]:
        path = Path(path).absolute()
        parsed_data = parse_yml(path)
        
        text_units = {}
        if len(parsed_data) == 0:
            logging.error(f"No localization data found in {path}.")
            return text_units
        else:
            path_key = delocalized_path(path) if delocalize_path else path.as_posix()
            text_units = {key: TextUnit(path_key, (key,), value) for key, value in parsed_data.items()}
        return text_units
    
    @override
    def extract_file(self, path: str | Path) -> list[TextUnit]:
        return list(self._extract_file(path).values())
    
    def _extract_lang_dir(self, lang_dir: Path, max_workers:Optional[int]=None) -> dict[str, dict[str, TextUnit]]:
        text_units = {}
        with ThreadPoolExecutor(max_workers) as executor:
            future_to_file = {executor.submit(self._extract_file, file_path): file_path for file_path in lang_dir.rglob("*.yml")}
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    units = future.result()
                    text_units[next(iter(units.values())).file] = units
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
        return text_units
    
    @override
    def extract_dir(self, path: str | Path, source_lang: str='en', target_lang: str='en', *args, **kwargs) -> list[TextUnit]:
        path = Path(path).absolute()
        source_lang=code2lang.get(source_lang, source_lang)
        target_lang=code2lang.get(target_lang, target_lang)
        if source_lang not in get_args(AvailableLanguage):
            logger.warning(f"Source language '{source_lang}' is not a supported language. Defaulting to 'english'. Supported languages are: {get_args(AvailableLanguage)}")
            source_lang = 'english'
        if target_lang not in get_args(AvailableLanguage):
            logger.warning(f"Target language '{target_lang}' is not a supported language. Defaulting to 'english'. Supported languages are: {get_args(AvailableLanguage)}")
            target_lang = source_lang
        if not path.is_dir():
            raise ValueError(f"Path {path} is not a directory.")
        elif not (path/"localization"/source_lang).is_dir(): 
            raise FileNotFoundError(f"Localization folder for language '{source_lang}' not found in {path}. Expected a 'localization/{source_lang}' subfolder.")
        if not (path/"descriptor.mod").exists():
            logger.warning(f"descriptor.mod file not found in {path}. This may not be a valid CK3 mod directory. Expected a 'descriptor.mod' file in the root of the directory.")
        elif not (path/"localization").is_dir():
            raise UnsupportedDirectoryError(f"Unsupported directory structure for {path}. Expected a mod directory with a 'localization' folder containing language subfolders.")
        
        source_units = self._extract_lang_dir(path / "localization" / source_lang, *args, **kwargs)
        if target_lang == source_lang:
            return [unit for units in source_units.values() for unit in units.values()]

        target_units = self._extract_lang_dir(path / "localization" / target_lang, *args, **kwargs)
        
        merged_units: list[TextUnit] = []
        for file_path in (source_units.keys() | target_units.keys()):
            merged_units.extend(merge_units(source_units.get(file_path, {}), target_units.get(file_path, {})))
            
        return merged_units
            
    def _apply_file(self, file_path: str | Path, text_units: list[TextUnit]|DataFrame, target_lang: AvailableLanguage, save_path: Optional[Path|str] = None, **kwargs) -> bool:  
        file_path = Path(file_path).absolute()
        save_path = Path(save_path).absolute() if save_path else file_path
        # Create a dictionary from the text_units
        # translation_dict = {unit.key.parts[-1]: unit.translation for unit in text_units}
        # Extract the language from the file name
        file_path = Path(str(file_path).format(target_lang)) # ensure the file path is formatted with the target language
        assert file_path.as_posix().endswith(f"l_{target_lang}.yml"), f"File name must end with l_{target_lang}.yml"
        if isinstance(text_units, list):
            text_units = DataFrame(text_units)
        with open(file_path, 'w', encoding='utf-8-sig') as f:
            f.write(f"l_{target_lang}:\n")
            text_units = text_units.set_index('key')
            for key, row in text_units.iterrows():
                if isinstance(key, JsonPath):
                    key = key.parts[-1]  # Use the last part of the JsonPath as the key
                # Escape quotes in the value
                escaped_value = row['translation'].replace('"', r'\"')
                # the version number is not needed, so we can just write the key without it
                f.write(f'  {key}: "{escaped_value}"\n')
        return True
    
    def _apply_dir(
        self, dir_path: str | Path, text_units: list[TextUnit]|DataFrame, 
        target_lang: AvailableLanguage,
        save_path: Optional[Path|str] = None, 
        **kwargs
    ) -> bool:
        if isinstance(text_units, list):
            text_units = DataFrame(text_units)
        # Group text_units by file path
        grouped_units = text_units.groupby('file')
        save_path = Path(save_path or dir_path).absolute()
        for _file_path, group in grouped_units:
            file_path = save_path / str(_file_path).format(lang = target_lang)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._apply_file(file_path, group, save_path=save_path, target_lang=target_lang, **kwargs)
        return True
        
    @override
    def apply_translations(
        self, file_path: str | Path, 
        text_units: list[TextUnit]|DataFrame, 
        save_path: Optional[Path|str] = None, 
        target_lang: Optional[str] = None, **kwargs
    )->bool:
        target_lang = code2lang.get(target_lang, target_lang) if target_lang else None
        if target_lang is None or not is_available_language(target_lang):
            raise ValueError(f"Target language '{target_lang}' is not a supported language. Supported languages are: {get_args(AvailableLanguage)}")
        file_path = Path(str(file_path).format(lang=target_lang)) if target_lang else Path(file_path)
        if file_path.is_dir():
            return self._apply_dir(file_path, text_units, target_lang, save_path, **kwargs)
        return self._apply_file(file_path, text_units, target_lang, save_path, **kwargs)


    
    
            
        
            