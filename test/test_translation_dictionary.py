from core.text_unit import JsonPath
from core.translation.dictionary import TranslationDictionary, format2regex
import pandas as pd
import re

class TestSaveLoadDictionary():
    def test_format2regex(self):
        format_str = "{file_name}_{source_lang}_{target_lang}.csv"
        regex_pattern = format2regex(format_str)
        expected_pattern = r"(?P<file_name>.+)_(?P<source_lang>.+)_(?P<target_lang>.+)\.csv"
        assert regex_pattern == expected_pattern, f"Expected: {expected_pattern}, Got: {regex_pattern}"
        
    def test_file_name_parsing(self):
        file_name = "example_with_underscores_en_es.csv"
        pattern = format2regex(TranslationDictionary.DEFAULT_FILE_NAME_FORMAT)
        match = re.match(pattern, file_name)
        assert match is not None, "Regex did not match the file name"
        assert match.group("source_lang") == "en", f"Expected source_lang: 'en', Got: '{match.group('source_lang')}'"
        assert match.group("target_lang") == "es", f"Expected target_lang: 'es', Got: '{match.group('target_lang')}'"

    def test_save_load_json_path(self):
        test_df = pd.DataFrame({
            "json_path": [JsonPath.from_list(["key1", "key2",1,"1"]), JsonPath.from_list(["key3", "key4",2,"2"])]
        })
        # Simulate saving to CSV and loading back
        test_df.to_csv("test_json_path_en_en.csv", index=False)
        dictionary = TranslationDictionary("test_json_path_en_en.csv")
        assert dictionary.df["json_path"].iloc[0].to_list() == ["key1", "key2",1,"1"], f"Expected: ['key1', 'key2',1,'1'], Got: {dictionary.df['json_path'].iloc[0].to_list()}"
        # delete the test file after the test
        import os
        os.remove("test_json_path_en_en.csv")
        

if __name__ == "__main__":
    test_save_load = TestSaveLoadDictionary()
    test_save_load.test_format2regex()
    test_save_load.test_file_name_parsing()
    test_save_load.test_save_load_json_path()