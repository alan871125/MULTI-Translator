import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional
from core.translation.dictionary import TranslationDictionary
import logging
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
        self._create_table()
            
    def _create_table(self):
        # Create the main translations table
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS Translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file TEXT NOT NULL,
                key TEXT NOT NULL,
                original TEXT NOT NULL,
                UNIQUE (file, key)
            );
            CREATE INDEX IF NOT EXISTS idx_file_key ON Translations (file, key);
            CREATE INDEX IF NOT EXISTS idx_original ON Translations (original);
        """)
        # Create a separate table to track file updates and their last modified timestamps
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS FileUpdates (
                file TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.connection.commit()
        
        
    # def add_languages(self, languages: list[str]):
    #     # safely add new columns for each language and its level
    #     for lang in languages:
    #         self.cursor.execute(f'''
    #             ALTER TABLE Translations ADD COLUMN IF NOT EXISTS {lang} TEXT
    #         ''')
    #         self.cursor.execute(f'''
    #             ALTER TABLE Translations ADD COLUMN IF NOT EXISTS {lang}.level INTEGER
    #         ''')
            
    def get_translation(self, key: str, lang: str) -> Optional[tuple[str, int]]:
        """Returns the translation and level for a given key and language."""
        query = f"""
            SELECT "{lang}", "{lang}.level" FROM Translations WHERE key='{key}'
        """
        return self.cursor.execute(query).fetchone()
    def search_translation(self, original:str, lang:str,):
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
    
    def insert_from_dataframe(self, df: pd.DataFrame):
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

        sql = f"""
            INSERT INTO Translations ({quoted_cols})
            VALUES ({placeholders})
            ON CONFLICT(file, key) DO UPDATE SET
            {set_clause};
        """
        null_originals = df.original.isnull()
        if null_originals.any():
            logger.warning(f"Found {null_originals.sum()} rows with null 'original' values. These rows will be skipped.")
            df = df[~null_originals]
        # Extract rows as tuples instead of dicts to match standard positional (?) placeholders
        records = [tuple(row) for row in df.itertuples(index=False)]

        self.cursor.executescript("BEGIN TRANSACTION;")
        self.cursor.executemany(sql, records)
        self.connection.commit()
    
    def insert_from_translation_dictionary(self, translation_dict: TranslationDictionary):
        """Inserts records from a TranslationDictionary instance."""
        df = translation_dict.df.copy()
        df['key'] = df['key'].astype(str)  # Ensure keys are strings for SQLite
        self.insert_from_dataframe(df)
    
    def _update_file_timestamp(self, file_path: str|Path):
        """Updates the last modified timestamp for a given file in the FileUpdates table."""
        file_path = str(file_path)
        timestamp = Path(file_path).stat().st_mtime
        self.cursor.execute("""
            INSERT INTO FileUpdates (file, timestamp)
            VALUES (?, ?)
            ON CONFLICT(file) DO UPDATE SET timestamp=excluded.timestamp;
        """, (file_path, timestamp))
        self.connection.commit()
            
    def update_from_csv(self, csv_path: str|Path):
        # check the timestamp of the file and compare with the timestamp in the database
        csv_path = Path(csv_path)
        timestamp = csv_path.stat().st_mtime
        self.cursor.execute("SELECT timestamp FROM FileUpdates WHERE file=?", (str(csv_path),))
        row = self.cursor.fetchone()
        if row and row[0] == timestamp:
            logger.debug(f"File {csv_path} is up to date.")
            return
        d = TranslationDictionary.load(csv_path)
        self.insert_from_translation_dictionary(d)
        self._update_file_timestamp(csv_path)
        logger.debug(f"Inserted/Updated translations from {csv_path} into the database.")
        
    def query(self, query: str):
        """Executes a raw SQL query and returns the results."""
        self.cursor.execute(query)
        return self.cursor.fetchall()
        
        
if __name__ == "__main__":
    db = TranslationDictionaryDatabase("test_workspace/rimworld/dictionary.db")
    df = pd.read_csv("test_workspace/rimworld/dictionary/Abilities_oops.csv")
    db.insert_from_dataframe(df)
    pass