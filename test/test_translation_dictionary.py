import io
import re
import pytest
import pandas as pd
from pathlib import Path
import sqlite3
from core.translation.dictionary_database import TranslationDictionaryDatabase
from core.json_path import JsonPath
from core.translation.dictionary import TranslationDictionary, TranslationDictionaryLong, format2regex

csv_data_wide = """
file,original,en,en.level,zh-tw,zh-tw.level,key
Actors,Victor,Victor,1,維克多,3,$[1].name
Actors,Vic, Vic,1,維克,2,$[1].nickname
Actors,Anna,Anna,1,安娜,3,$[2].name
Actors,John,John,1,約翰,3,$[3].name
"""
csv_data_long = """
file,original,translation,level,key
Actors,Victor,維克多,1,$[1].name
Actors,Vic, 維克,1,$[1].nickname
Actors,Anna,安娜,1,$[2].name
Actors,John,約翰,1,$[3].name
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


class TestTranslationDictionaryDatabase:
    def test_update_from_csv_existing_database_without_unique_index(self, tmp_path):

        db_path = tmp_path / "test.db"
        # Create an existing database table that lacked UNIQUE constraint on file
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE DictionaryFileState (
                sha256 BLOB PRIMARY KEY,
                file TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE Translations (
                id INTEGER PRIMARY KEY,
                file TEXT NOT NULL,
                key TEXT NOT NULL,
                original TEXT NOT NULL,
                UNIQUE (file, key)
            );
        """)
        conn.commit()
        conn.close()

        csv_path = tmp_path / "Actors.csv"
        csv_path.write_text(csv_data_wide.strip(), encoding="utf-8")

        # Initializing TranslationDictionaryDatabase should automatically create the unique index and succeed
        db = TranslationDictionaryDatabase(db_path)
        res = db.load_csv(csv_path)
        assert res is not None

        # Updating again should recognize it is up to date without error
        res_cached = db.load_csv(csv_path)
        assert res_cached is None
    
    @pytest.fixture
    def test_db_load_csv(self) -> TranslationDictionaryDatabase:
        db_in_memory = ":memory:"
        db = TranslationDictionaryDatabase(db_in_memory)
        csv_path = Path("test/.data/dictionary/Actors.csv")
        db.load_csv(csv_path)
        return db
    
    def test_search_translation(self, test_db_load_csv):
        db = test_db_load_csv
        # Search for a translation that exists
        results = db.search_translations("Victor", "zh-tw")
        assert len(results) > 0, "Expected to find at least one translation for 'Victor'"
        assert any(res[0] == "維克多" for res in results), "Expected to find translation '維克多' for 'Victor'"
    
    def test_get_translation(self, test_db_load_csv):
        db = test_db_load_csv
        # Search for a translation that exists
        result = db.get_translation(key="$[1].name",lang="zh-tw")
        assert result is not None, "Expected to find translation for 'Victor'"
        assert result == ("維克多", 3), f"Expected translation and level ('維克多', 3), got {result}"
    
    def test_fuzzy_matching(self, test_db_load_csv):
        db = test_db_load_csv
        # Fuzzy search for a translation that exists
        results = db.get_fuzzy_matches("Viktor", "zh-tw", th=80)
        assert len(results) > 0, "Expected to find at least one fuzzy match for 'Viktor'"
        print(f"Fuzzy matches for 'Viktor': {results}, type: {type(results)}")
        print(f"Fuzzy matches for 'Viktor': {list[results]}")
        assert any(res[0:2] == ("Victor","維克多") for res in results), "Expected to find fuzzy match translation '維克多' for 'Viktor'"
    
    def test_unload_csv(self, test_db_load_csv):
        db = test_db_load_csv
        csv_path = Path("test/.data/dictionary/Actors.csv")
        # Unload the CSV and check that the file is removed from the database
        db.unload_csv(csv_path)
        db.cursor.execute("SELECT * FROM DictionaryFileState WHERE file = ?", (str(csv_path),))
        result = db.cursor.fetchone()
        assert result is None, "CSV file was not removed from the database"
        
        db.cursor.execute("SELECT * FROM Translations WHERE file = ?", (str(csv_path),))
        translations_result = db.cursor.fetchall()
        assert translations_result == [], "Translations were not removed from the database"
        
        # The Translations and DictionaryFileState tables should be empty:
        file_state_table = db.cursor.execute("SELECT * FROM DictionaryFileState").fetchall()
        assert file_state_table == [], "DictionaryFileState table is not empty after unloading CSV"
        translation_table = db.cursor.execute("SELECT * FROM Translations").fetchall()
        assert translation_table == [], "Translations table is not empty after unloading CSV"
        
        # close the database connection
        db.connection.close()


if __name__ == "__main__":
    test_save_load = TestSaveLoadDictionaryLong()
    test_save_load.test_format2regex()
    test_save_load.test_file_name_parsing()
    test_save_load.test_save_load_json_path()