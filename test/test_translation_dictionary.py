import io
import re
import pandas as pd
from pathlib import Path
from core.json_path import JsonPath
from core.translation.dictionary import TranslationDictionary, TranslationDictionaryLong, format2regex

csv_data_wide = """
file,original,en,en.level,zh-tw,zh-tw.level,key
Actors,Victor,Victor,1,維克多,3,"[1,""name""]"
Actors,Vic, Vic,1,維克,2,"[1,""nickname""]"
Actors,Anna,1,安娜,3,"[2,""name""]"
Actors,John,1,約翰,3,"[3,""name""]"
"""
csv_data_long = """
file,original,translation,level,key
Actors,Victor,維克多,1,"[1,""name""]"
Actors,Vic, 維克,1,"[1,""nickname""]"
Actors,Anna,安娜,1,"[2,""name""]"
Actors,John,約翰,1,"[3,""name""]"
"""
class TestTranslationDictionary:
    def test_translation_dictionary_init(self):
        df = pd.read_csv(io.StringIO(csv_data_wide))
        dictionary = TranslationDictionary(df=df, source_lang="en", target_lang="zh-tw")
        assert dictionary.source_lang == "en"
        assert dictionary.target_lang == "zh-tw"
        assert set(dictionary.languages) == {"en", "zh-tw"}
        en_df = dictionary["en"]
        assert list(en_df.columns) == TranslationDictionary.REQUIRED_COLUMNS + ["en", "en.level"]
        zh_tw_df = dictionary["zh-tw"]
        assert list(zh_tw_df.columns) == TranslationDictionary.REQUIRED_COLUMNS + ["zh-tw", "zh-tw.level"]

class TestSaveLoadDictionaryLong():
    def test_format2regex(self):
        format_str = "{file_name}_{source_lang}_{target_lang}.csv"
        regex_pattern = format2regex(format_str)
        expected_pattern = r"(?P<file_name>.+)_(?P<source_lang>.+)_(?P<target_lang>.+)\.csv"
        assert regex_pattern == expected_pattern, f"Expected: {expected_pattern}, Got: {regex_pattern}"
        
    def test_file_name_parsing(self):
        file_name = "example_with_underscores_en_es.csv"
        pattern = format2regex(TranslationDictionaryLong.DEFAULT_FILE_NAME_FORMAT)
        match = re.match(pattern, file_name)
        assert match is not None, "Regex did not match the file name"
        assert match.group("source_lang") == "en", f"Expected source_lang: 'en', Got: '{match.group('source_lang')}'"
        assert match.group("target_lang") == "es", f"Expected target_lang: 'es', Got: '{match.group('target_lang')}'"

    def test_save_load_json_path(self):
        test_df = pd.DataFrame({
            "key": [JsonPath(["key1", "key2",1,"1"]), JsonPath(["key3", "key4",2,"2"])]
        })
        # Simulate saving to CSV and loading back
        test_df.to_csv("test_json_path_en_en.csv", index=False)
        dictionary = TranslationDictionaryLong("test_json_path_en_en.csv")
        assert dictionary.df["key"].iloc[0].parts == ["key1", "key2",1,"1"], f"Expected: ['key1', 'key2',1,'1'], Got: {dictionary.df['json_path'].iloc[0].parts}"
        # delete the test file after the test
        import os
        os.remove("test_json_path_en_en.csv")

    def test_save_csv_literal(self, tmp_path):
        df = pd.read_csv(io.StringIO(csv_data_long))
        dictionary = TranslationDictionaryLong(df=df, source_lang="en", target_lang="zh-tw")
        save_path = tmp_path / "custom_name.csv"
        dictionary.save_csv(save_path, use_convention=False)
        assert save_path.exists()
        loaded_df = pd.read_csv(save_path)
        assert loaded_df.equals(dictionary.df), "Loaded DataFrame does not match the original"

    def test_save_csv_convention(self, tmp_path):
        import io
        df = pd.read_csv(io.StringIO(csv_data_long))
        dictionary = TranslationDictionaryLong(df=df, source_lang="en", target_lang="zh-tw")
        base_path = tmp_path / "Actors.json"
        actual_path = dictionary.save_csv(base_path, use_convention=True)
        assert actual_path.name == "Actors_en_zh-tw.csv"
        assert actual_path.exists()

    def test_get_conventional_path(self):
        dictionary = TranslationDictionaryLong(source_lang="en", target_lang="zh-tw")
        base_path = Path("data/Actors.json")
        assert dictionary.get_conventional_path(base_path) == Path("data/Actors_en_zh-tw.csv")

    def test_custom_format_init(self):
        custom_format = "DICT_{file_name}_{source_lang}_{target_lang}.csv"
        dictionary = TranslationDictionaryLong(source_lang="en", target_lang="zh-tw", file_name_format=custom_format)
        base_path = Path("data/Actors.json")
        assert dictionary.get_conventional_path(base_path) == Path("data/DICT_Actors_en_zh-tw.csv")
        

if __name__ == "__main__":
    test_save_load = TestSaveLoadDictionaryLong()
    test_save_load.test_format2regex()
    test_save_load.test_file_name_parsing()
    test_save_load.test_save_load_json_path()