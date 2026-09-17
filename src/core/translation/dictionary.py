import re
from pathlib import Path
from typing import Optional, Literal, Union, Callable
from rapidfuzz import process, fuzz
import pandas as pd
from ..json_path import JsonPath
from .label import TranslationLabel
import logging
logger = logging.getLogger(__name__)

def format2regex(format_str: str) -> str:
    """Converts a format string with placeholders (e.g., {source_lang}, {target_lang}) into a regex pattern.
    """
    format_str = format_str.replace(".", r"\.")
    regex_pattern = re.sub("{(?P<name>[^}]+)}", r"(?P<\g<name>>.+)", format_str)
    # Escape dots in the file extension
    return regex_pattern

class TranslationDictionary:
    """A translation Dictionary in wide format,
    
    Each language takes 2 columns: {lang}, {lang}.level
    """
    # file: the file name where the text unit is located
    # json_path: the json path to locate the text unit in the file (unique key)
    # attribute: the attribute name of the text unit (e.g., name, description)
    # original: the original text in the source language (for reference)
    # {lang}: the translated text in the target language
    # {lang}.level: the translation level. see TranslationLevel for more details.
    REQUIRED_COLUMNS = ["file", "key", "original"]
    def __init__(self, df: pd.DataFrame, source_lang: Optional[str] = None, target_lang: Optional[str] = None):
        assert all(col in df.columns for col in self.REQUIRED_COLUMNS), f"DataFrame must contain the following columns: {self.REQUIRED_COLUMNS}"
        self.df = df
        if "translation" in df.columns and "level" in df.columns:
            assert target_lang is not None, "Provide target_lang or rename 'translation' and 'level' columns to include the target language (e.g., ('en','en.level'), ('zh-TW','zh-TW.level'))"
            # convert to long format:
            self.df.rename(columns={"translation": f"{target_lang}", "level": f"{target_lang}.level"}, inplace=True)
        self.source_lang = source_lang
        self.target_lang = target_lang

    @property
    def languages(self)->list[str]:
        """Returns a list of languages in the dictionary, excluding 'original'."""
        # find columns that end with .level and extract the language name
        cols = self.df.columns
        return [col[:-6] for col in cols if col.endswith(".level")]

    def get(self, lang: str) -> Optional[pd.DataFrame]:
        """Returns a DataFrame with columns: file, json_path, attribute, original, {lang}, {lang}.level"""
        if lang not in self.languages:
            logger.warning(f"Language '{lang}' not found in the dictionary. Available languages: {self.languages}")
            return None
        return self.df[self.REQUIRED_COLUMNS+[lang, f"{lang}.level"]]
    
    def __getitem__(self, lang: str) -> pd.DataFrame:
        """Returns a DataFrame with columns: file, json_path, attribute, original, {lang}, {lang}.level"""
        return self.df[self.REQUIRED_COLUMNS+[lang, f"{lang}.level"]]
        
    def save(self, file_path: str|Path):
        """Saves the dictionary to a CSV file."""
        file_path = Path(file_path).with_suffix(".csv")
        self.df.to_csv(file_path, index=False)
        logger.info(f"Dictionary saved to {file_path}")
    
    @classmethod
    def load(cls, file_path: str|Path, source_lang: Optional[str] = None, target_lang: Optional[str] = None, key_class:Optional[Callable[[str], object]] = None):
        """Loads the dictionary from a CSV file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if key_class is None:
            key_class = JsonPath
        df = pd.read_csv(
            file_path, converters={"key": key_class} if key_class else None, 
            # cast the columns to the correct types, preventing converting "None" to null
            dtype={"original":str, "translation":str, "level":int, "file":str}, keep_default_na=False
        )
        return cls(df=df, source_lang=source_lang, target_lang=target_lang)
    
    def check_difference(self, other:Union[pd.DataFrame, "TranslationDictionary"], self_type:Literal["old", "new"] = "old", verbose:bool = True)->dict[str, TranslationLabel]:
        """
        Arguments:
            other (pd.DataFrame): The new dictionary to compare against the old one.
            self_type (str): Whether `self` is the old dictionary or the new one. Accepts "old" or "new".
        """
        comments:dict[str,TranslationLabel] = {} 
        if isinstance(other, TranslationDictionary):
            other = other.df
        if self_type == "old":
            cur, new = self.df, other
            keys_old, keys_new = set(cur["key"]), set(new["key"])
            # 1. Mark DEPRECATED keys in old dictionary
            keys_deprecated = keys_old - keys_new
            for key in keys_deprecated:
                comments[key] = TranslationLabel.DEPRECATED
            if verbose:
                logger.info(f"Found {len(keys_deprecated)} deprecated keys")
        elif self_type == "new":
            cur, new = other, self.df
            keys_old, keys_new = set(cur["key"]), set(new["key"])
            # 2. Mark NEW keys in new dictionary
            keys_new_added = keys_new - keys_old
            if verbose:
                logger.info(f"Found {len(keys_new_added)} new keys")
            for key in keys_new_added:
                comments[key] = TranslationLabel.NEW
        else:
            raise ValueError(f"Invalid self_type: {self_type}. Must be 'old' or 'new'.")
        # 3. Mark UPDATED keys where original text differs
        old_org = cur.set_index("key")["original"]
        new_org = new.set_index("key")["original"]
        keys_both = list(keys_old & keys_new)
        updated = old_org[keys_both] != new_org[keys_both]
        if verbose:
            logger.info(f"Found {updated.sum()} updated keys: {updated[updated].index.astype(str).tolist()}")
        for key in updated[updated].index:
            comments[key] = TranslationLabel.UPDATED
        return comments


class TranslationDictionaryLong:
    # Deprecated: A translation Dictionary in long format, with columns: file, json_path, attribute, original, translation, level
    DEFAULT_FILE_NAME_FORMAT = "{file_name}_{source_lang}_{target_lang}.csv"
    
    def __init__(self, df: Optional[str|Path|pd.DataFrame] = None, source_lang: Optional[str] = None, target_lang: Optional[str] = None, file_name_format: Optional[str] = None):
        self.source_lang = source_lang or ""
        self.target_lang = target_lang or ""
        self.file_name_format = file_name_format or self.DEFAULT_FILE_NAME_FORMAT
        if isinstance(df, pd.DataFrame):
            self.df = df
        elif isinstance(df, (str, Path)):
            self.load_csv(df)
        else:
            self.df = pd.DataFrame()
            
    @classmethod
    def get_dictionary_path(cls, file_path: str|Path, source_lang: str, target_lang: str, file_name_format: Optional[str] = None) -> Optional[str]:
        """Get the file path of the dictionary associated with the given file name (tab)."""
        file_name = Path(file_path).stem
        file_name_format = file_name_format or cls.DEFAULT_FILE_NAME_FORMAT
        expected_file_name = file_name_format.format(file_name=file_name, source_lang=source_lang, target_lang=target_lang)
        expected_file_path = Path(file_path).parent / expected_file_name
        if expected_file_path.exists():
            return str(expected_file_path)
        return None
            
    def get_conventional_path(self, base_path: str|Path) -> Path:
        """Generates the conventional path based on the base path and stored format."""
        base_path = Path(base_path)
        file_name = self.file_name_format.format(
            file_name=base_path.stem, 
            source_lang=self.source_lang, 
            target_lang=self.target_lang
        )
        return base_path.parent / file_name

    def load_csv(self, file_path: str|Path, file_name_format: Optional[str] = None, key_class=JsonPath):
        """ loads a csv file with the required columns
        Obtains the source and target languages from the file name.
        
        default file_name format: {file_name}_{source_lang}_{target_lang}.csv
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        # Extract source and target languages from the file name using regex
        pattern = format2regex(file_name_format or self.file_name_format)
        if not (match:= re.match(pattern, file_path.name)):
            raise ValueError(f"File name does not match expected format: {file_path.name}")
        self.source_lang = match.group("source_lang")
        self.target_lang = match.group("target_lang")
        # Load the CSV file into a DataFrame
        self.df:pd.DataFrame = pd.read_csv(file_path, converters={"key": key_class})
        
    def save_csv(self, file_path: str|Path, use_convention: bool = False):
        """Saves the current translation table to a CSV file.
        
        Arguments:
            file_path (str|Path): The target file path.
            use_convention (bool): If True, formats the filename using get_conventional_path.
                                  If False (default), saves exactly to file_path.
        """
        if self.df.empty:
            raise ValueError("Translation table is empty. Nothing to save.")
        
        full_path = Path(file_path)
        if use_convention:
            full_path = self.get_conventional_path(full_path)
            
        self.df.to_csv(full_path, index=False)
        logger.debug("Dictionary saved as: %s", full_path)
        return full_path

    def fuzzy_lookup(self, text: str, limit=5, score_cutoff=70):
        """Returns a list of tuples (key, value, score) for the best matches to the input text.
        Cache the results to improve performance for repeated lookups of the same text.
        """
        if self.df.empty:
            return []
        matches = process.extract(text, self.df[self.source_lang], scorer=fuzz.ratio, limit=limit, score_cutoff=score_cutoff)
        return [(match[0], self.df.loc[match[2], self.target_lang], match[1]) for match in matches]

if __name__ == "__main__":
    pass