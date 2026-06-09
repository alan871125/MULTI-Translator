import re
from pathlib import Path
from typing import Optional
from rapidfuzz import process, fuzz
import pandas as pd

from ..text_unit import JsonPath

def format2regex(format_str: str) -> str:
    """Converts a format string with placeholders (e.g., {source_lang}, {target_lang}) into a regex pattern.
    """
    format_str = format_str.replace(".", r"\.")
    regex_pattern = re.sub("{(?P<name>[^}]+)}", r"(?P<\g<name>>.+)", format_str)
    # Escape dots in the file extension
    return regex_pattern

class TranslationDictionary:
    DEFAULT_FILE_NAME_FORMAT = "{file_name}_{source_lang}_{target_lang}.csv"
    
    def __init__(self, df: Optional[str|Path|pd.DataFrame] = None,source_lang: Optional[str] = None, target_lang: Optional[str] = None):
        self.source_lang = source_lang or ""
        self.target_lang = target_lang or ""
        if isinstance(df, pd.DataFrame):
            self.df = df
        elif isinstance(df, (str, Path)):
            self.load_csv(df)

            
    def load_csv(self, file_path: str|Path, file_name_format: Optional[str] = None):
        """ loads a csv file with the required columns
        Obtains the source and target languages from the file name.
        
        default file_name format: {file_name}_{source_lang}_{target_lang}.csv
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        # Extract source and target languages from the file name using regex
        pattern = format2regex(file_name_format or self.DEFAULT_FILE_NAME_FORMAT)
        if not (match:= re.match(pattern, file_path.name)):
            raise ValueError(f"File name does not match expected format: {file_path.name}")
        self.source_lang = match.group("source_lang")
        self.target_lang = match.group("target_lang")
        # Load the CSV file into a DataFrame
        self.df:pd.DataFrame = pd.read_csv(file_path, converters={"json_path": JsonPath})
        
    def save_csv(self, file_path: str|Path, file_name_format: Optional[str] = None):
        """Saves the current translation table to a CSV file.
        The file name is generated based on the source and target languages using the specified format.
        """
        if self.df.empty:
            raise ValueError("Translation table is empty. Nothing to save.")
        file_path = Path(file_path)
        file_name_format = file_name_format or self.DEFAULT_FILE_NAME_FORMAT
        file_name = file_name_format.format(file_name=file_path.stem, source_lang=self.source_lang, target_lang=self.target_lang)
        full_path = file_path.parent / file_name
        self.df.to_csv(full_path, index=False)
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