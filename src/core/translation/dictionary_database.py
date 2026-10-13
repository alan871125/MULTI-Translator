import sqlite3
import logging
import pandas as pd
from rapidfuzz import fuzz
from pathlib import Path
from typing import Optional

from ..file_state import FileState
from .dictionary import TranslationDictionary

logger = logging.getLogger(__name__)

class TranslationDictionaryDatabase:
    """A translation Dictionary in wide format,
        
    Each language takes 2 columns: {lang}, {lang}.level
    """
    # REQUIRED_COLUMNS = ["file", "key", "original"]
    def __init__(self, db_path):
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path)
        self.cursor = self.connection.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON;")
        self._create_table()
        self.connection.create_function("fuzz_score", 2, lambda a, b: fuzz.WRatio(a, b))
        
    def _create_table(self):
        self.cursor.execute("PRAGMA foreign_keys = ON;")
        # Create the main translations table
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS DictionaryFileState (
                sha256 BLOB PRIMARY KEY,
                file TEXT UNIQUE NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS Translations (
                id INTEGER PRIMARY KEY,
                file TEXT NOT NULL,
                key TEXT NOT NULL,
                original TEXT NOT NULL,
                dictionary_source BLOB
                    REFERENCES DictionaryFileState(sha256)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,
                UNIQUE (file, key)
            );

            CREATE INDEX IF NOT EXISTS idx_original
                ON Translations (original);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_file_state_file
                ON DictionaryFileState (file);
        """)

        # Ensure dictionary_source column exists in Translations for older databases
        self.cursor.execute("PRAGMA table_info(Translations)")
        existing_cols = {row[1] for row in self.cursor.fetchall()}
        if "dictionary_source" not in existing_cols:
            self.cursor.execute("""
                ALTER TABLE Translations ADD COLUMN dictionary_source BLOB
                    REFERENCES DictionaryFileState(sha256)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE
            """)

        self.connection.commit()
        
    def _update_db(self):
        """Verifies the integrity of loaded dictionaries by checking their SHA256 hashes and timestamps. 
        Then updates with the corresponding file if the dictionary file has changed since the last recorded state.
        """
        self.cursor.execute("SELECT sha256, file, timestamp FROM DictionaryFileState")
        rows = self.cursor.fetchall()
        for sha256, file, timestamp in rows:
            file_path = Path(file)
            current_state = FileState.from_path(file_path)
            if not current_state.validate(sha256=sha256, mtime_ns=timestamp):
                logger.debug(f"Dictionary file {file_path} has changed. Updating database.")
                self.unload_csv(file_path)
                self.load_csv(file_path)
                self.connection.commit()
    
    def get_loaded_dictionaries(self) -> list[Path]:
        """Returns a list of loaded dictionary sources with their file states."""
        self.cursor.execute("SELECT sha256, file, timestamp FROM DictionaryFileState")
        rows = self.cursor.fetchall()
        return [Path(row[1]).absolute() for row in rows]
    
    def get_translation(self, key: str, lang: str) -> Optional[tuple[str, int]]:
        """Returns the translation and level for a given key and language."""
        query = f"""
            SELECT "{lang}", "{lang}.level" FROM Translations WHERE key='{key}'
        """
        return self.cursor.execute(query).fetchone()
    
    def get_fuzzy_matches(self, original: str, lang: str, th:int=70, limit: int = 10, min_lv=0) -> list[tuple[str, str, int]]:
        query = f"""
            SELECT original, "{lang}", fuzz_score(original, ?) AS score, "{lang}.level" AS lv
            FROM Translations
            WHERE score >= ? AND lv>{min_lv}
            ORDER BY score DESC, lv DESC
            LIMIT {limit}
        """
        return self.cursor.execute(query, (original, th)).fetchall()
        
    def search_translations(self, original:str, lang:str,):
        q = f"""
            SELECT "{lang}", "{lang}.level" FROM Translations WHERE original LIKE '%{original}%'
        """
        return self.cursor.execute(q).fetchall()
    
    def ensure_columns_exist(self, columns: list[str]):
        """Dynamically add missing language columns to SQLite schema."""
        self.cursor.execute("PRAGMA table_info(Translations)")
        existing_cols = {row[1] for row in self.cursor.fetchall()}

        for col in columns:
            if col not in existing_cols and col != "id":
                # Determine type: level columns are INTEGER, others TEXT
                col_type = "INTEGER" if col.endswith(".level") else "TEXT"
                # Sanitize column name with double quotes for characters like hyphen/dot
                self.cursor.execute(
                    f'ALTER TABLE Translations ADD COLUMN "{col}" {col_type}'
                )
        self.connection.commit()
        
    def add_dictionary_source(self, file_path: str | Path):
        """Adds a new dictionary source to the DictionaryFileState table."""
        file_path = Path(file_path).absolute()
        file_state = FileState.from_path(file_path)
        self.cursor.execute("""
            INSERT INTO DictionaryFileState (sha256, file, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(file) DO UPDATE SET timestamp=excluded.timestamp, sha256=excluded.sha256;
        """, (file_state.sha256, file_path.as_posix(), file_state.mtime_ns))
        self.connection.commit()
        return file_state
    
    def insert_from_dataframe(self, df: pd.DataFrame, dictionary_source: Optional[Path] = None):
        """Directly inserts records using parameterized SQL, double-quoting all column names."""
        # 1. Ensure columns exist in SQLite database
        self.ensure_columns_exist(df.columns.tolist())

        cols = df.columns.tolist()
        # 2. Prepare the SQL statement with double-quoted column names and placeholders
        quoted_cols = ", ".join([f'"{c}"' for c in cols])
        placeholders = ", ".join(["?"] * len(cols))

        # Build the ON CONFLICT clause safely double-quoted
        update_cols = [c for c in cols if c not in ("file", "key")]
        set_clause = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in update_cols])
        null_originals = df.original.isnull()
        if null_originals.any():
            logger.warning(f"Found {null_originals.sum()} rows with null 'original' values. These rows will be skipped.")
            df = df[~null_originals]
            
        if dictionary_source:
            file_state = self.add_dictionary_source(dictionary_source)
            # Append the dictionary_source to each record
            sql = f"""
                INSERT INTO Translations ({quoted_cols}, dictionary_source)
                VALUES ({placeholders}, ?)
                ON CONFLICT(file, key) DO UPDATE SET
                {set_clause};
            """
            records = [tuple(row) + (file_state.sha256,) for row in df.itertuples(index=False)]
        else:
            sql = f"""
                INSERT INTO Translations ({quoted_cols})
                VALUES ({placeholders})
                ON CONFLICT(file, key) DO UPDATE SET
                {set_clause};
            """
            # Extract rows as tuples instead of dicts to match standard positional (?) placeholders
            records = [tuple(row) for row in df.itertuples(index=False)]

        self.cursor.executescript("BEGIN TRANSACTION;")
        self.cursor.executemany(sql, records)
        self.connection.commit()
    
    def insert_from_translation_dictionary(self, translation_dict: TranslationDictionary, dictionary_source: Optional[Path] = None):
        """Inserts records from a TranslationDictionary instance."""
        df = translation_dict.df.copy()
        languages = translation_dict.languages
        mask = df['original'].notnull() & df['key'].notnull()
        # keep only the top-level translations for each language
        for lang in languages:
            df_sorted = df.sort_values(by=["original",f"{lang}.level"], ascending=True)
            df_top_unique = df_sorted.drop_duplicates(subset="original", keep="last")
            mask &= df.index.isin(df_top_unique.index)
        df = df[mask]
        df['key'] = df['key'].astype(str)  # Ensure keys are strings for SQLite
        self.insert_from_dataframe(df, dictionary_source=dictionary_source)
    
    def _update_file_state(self, file_path: str|Path):
        """Updates the last modified timestamp for a given file in the DictionaryFileState table."""
        file_path = Path(file_path).absolute()
        file_state = FileState.from_path(file_path)
        self.cursor.execute("""
            INSERT INTO DictionaryFileState (sha256, file, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(file) DO UPDATE SET timestamp=excluded.timestamp, sha256=excluded.sha256;
        """, (file_state.sha256, file_path.as_posix(), file_state.mtime_ns))
        self.connection.commit()
            
    def load_csv(self, csv_path: str|Path):
        # check the timestamp of the file and compare with the timestamp in the database
        csv_path = Path(csv_path).absolute()
        file_state = FileState.from_path(csv_path)
        self.cursor.execute("SELECT * FROM DictionaryFileState WHERE file=?", (csv_path.as_posix(),))
        row = self.cursor.fetchone()
        if row and file_state.validate(sha256=row[0], mtime_ns=row[2]):
            logger.debug(f"CSV file {csv_path} is up to date in the database. No update needed.")
            return None  # No update needed
        d = TranslationDictionary.load(csv_path)
        self.insert_from_translation_dictionary(d, dictionary_source=csv_path)
        self._update_file_state(csv_path)
        logger.debug(f"Inserted/Updated translations from {csv_path} into the database.")
        return d
    
    def unload_csv(self, csv_path: str|Path):
        """Removes all translations associated with a specific CSV file from the database."""
        csv_path = Path(csv_path).absolute().as_posix()
        self.cursor.execute("DELETE FROM DictionaryFileState WHERE file=?", (csv_path,))
        # self.cursor.execute("DELETE FROM Translations WHERE file=?", (csv_path.as_posix(),))
        self.connection.commit()
        logger.debug(f"Removed translations and file state for {csv_path} from the database.")
        
    def query(self, query: str):
        """Executes a raw SQL query and returns the results."""
        self.cursor.execute(query)
        return self.cursor.fetchall()
