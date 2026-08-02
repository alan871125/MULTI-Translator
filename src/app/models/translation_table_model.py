


import logging
import pandas as pd
from pathlib import Path
from typing import Any, Iterable, Literal, cast, override, Optional

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QUndoCommand, QUndoStack
from config import settings
from core.engines._base import BaseExtractor
from core.text_unit import TextUnit
from core.translation import TranslationDictionary, TranslationLevel, batch_chinese_convertion
from app.gui.dialogs.search import TableFilters
from app.gui.theme import ThemeManager
from app.language import LanguagePack

logger = logging.getLogger(__name__)
L = LanguagePack()

class TranslationTableModel(QAbstractTableModel):
    _COLUMNS = ["file", "key", "original", "translation"]
    _HIDDEN_COLUMNS = ["level"]  # Columns that are not displayed but used for internal logic, such as translation level
    def __init__(self, data=None, filters:Optional[TableFilters] = None, file_path: Optional[Path|str] = None, engine:Optional[BaseExtractor] = None, undo_stack: Optional[QUndoStack] = None):
        super().__init__()
        self.file_path = Path(file_path) if file_path else None
        self.engine = engine
        self.undo_stack = undo_stack
        self.df:pd.DataFrame = pd.DataFrame(data or [], columns=self._COLUMNS+self._HIDDEN_COLUMNS)
        self._filtered_df = None
        self._mask_indexes = None
        self.filters = filters if filters is not None else TableFilters()
        self.filters.text_filter_changed.connect(self.on_filter_changed)
        self.filters.level_filter_changed.connect(self.on_filter_changed)
        self.post_init_check()
        
    def post_init_check(self):
        if self.file_path is None:
            logger.warning("TranslationTableModel initialized without a file path. Some operations may not work (ie., loading/saving files).")
        if self.engine is None:
            logger.warning("TranslationTableModel initialized without an engine. Some operations may not work (ie., loading/saving files).")
        if self.filters is None:
            logger.warning("TranslationTableModel initialized without filters. Filters are Initialized with default empty filters, but may be disconnected from other components.")
        
    def _level_from_value(self, value):
        if isinstance(value, TranslationLevel):
            return value
        if pd.isna(value):
            return TranslationLevel.UNTRANSLATED
        return TranslationLevel(value)

    @override
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._COLUMNS):
                return L[self._COLUMNS[section]]
        return section + 1

    def load_units(self, units: list[TextUnit]):
        """Load a list of TextUnit objects(dataclass), and convert them into the internal DataFrame format for the model."""
        data = pd.DataFrame(units, columns=self._COLUMNS+self._HIDDEN_COLUMNS)

        self.df = pd.concat([self.df, data], ignore_index=True)

    def get_units(self) -> list[TextUnit]:
        """Convert the internal DataFrame back into a list of TextUnit objects."""
        # Using cast to satisfy the static analyzer that keys are strings
        records = cast(list[dict[str, Any]], self.df.to_dict(orient='records'))
        return [TextUnit(**row) for row in records]

    def load_from_file(self):
        """Extract units from the bound file_path using the bound engine."""
        if not self.file_path or not self.engine:
            logger.error("Cannot load: file_path or engine not set.")
            return
        units = self.engine.extract_file(self.file_path)
        self.load_units(units)

    def save_to_file(self, save_path: Optional[Path|str] = None):
        """Complete and apply translations back to the file using the bound engine."""
        if not self.file_path or not self.engine:
            logger.error("Cannot save: file_path or engine not set.")
            return

        save_path = save_path or Path(settings.output_dir) / self.file_path.name
        units = self.get_units()
        self.engine.apply_translations(self.file_path, units, save_path=save_path, target_lang=settings.TARGET_LANG)
        logger.info(f"Saved translations to {save_path}")

    @override
    def rowCount(self, parent=QModelIndex()):
        return len(self.filtered_df)
    @override
    def columnCount(self, parent=QModelIndex()):
        return len(self._COLUMNS)
    @override
    def data(self, index, role=Qt.DisplayRole):
        theme = ThemeManager.theme

        if not index.isValid():
            return None
        r = index.row()
        c = index.column()

        if ((role == Qt.BackgroundRole and theme.USE_COLOR_LEVEL_BACKGROUND) or
            (role == Qt.ForegroundRole and not theme.USE_COLOR_LEVEL_BACKGROUND) ):
            if r < 0 or r >= len(self.filtered_df):
                return None
            row = self.filtered_df.iloc[r]
            level = self._level_from_value(row.level)
            return QColor(ThemeManager.theme.get_level_color(level))

        if role in (Qt.DisplayRole, Qt.EditRole):
            if r < 0 or r >= len(self.filtered_df):
                return None
            if c < 0 or c >= len(self._COLUMNS):
                return None
            row = self.filtered_df.iloc[r]
            col = self._COLUMNS[c]
            if col =='key':
                return str(row.get(col, ""))
            return row.get(col, "")
        return None

    @override
    def setData(self, index, value, role=Qt.EditRole):
        # Support inline editing from the view for the Translation column
        if role != Qt.EditRole or not index.isValid():
            return False
        row = index.row()
        col = index.column()
        try:
            col_name = self._COLUMNS[col]
        except Exception:
            return False
        if col_name != "translation":
            return False
        text = str(value)
        # locate original value from filtered data
        if row < 0 or row >= len(self.filtered_df):
            return False
        original = self.filtered_df.iloc[row].get("original")
        if original is None:
            return False
        
        idx = self.get_true_indexes([row])
        level = TranslationLevel.VERIFIED if text else TranslationLevel.UNTRANSLATED
        
        if self.undo_stack is not None: # if not connected to a session's undo stack, apply changes directly without undo support
            self.undo_stack.push(TranslationCommand(
                model=self,
                idxs=idx,
                translations=[text],
                levels=level,
                description=f"Inline Edit"
            ))
        else:
            self.set_translations(idx, [text], levels=level)
        return True
    
    @override
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        # make items selectable and enabled; only the Translation column is editable
        col = index.column()
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        try:
            if self._COLUMNS[col] == "translation":
                flags |= Qt.ItemIsEditable
        except Exception:
            pass
        return flags

    # ----- Filtering -----
    def on_filter_changed(self):
        self.beginResetModel()
        self._mask_indexes = None
        self._filtered_df = None
        self.endResetModel()

    @property
    def filter_mask(self) -> pd.Series:
        if self._mask_indexes is not None:
            mask = pd.Series([False] * len(self.df), index=self.df.index)
            mask[self._mask_indexes] = True
        else:
            mask=self.filters.build_mask(self.df)
            self._mask_indexes = mask[mask].index
        return mask

    @property
    def filtered_df(self) -> pd.DataFrame:
        if not self.filters.is_filtering:
            return self.df

        if self._filtered_df is not None:
            return self._filtered_df

        mask = self.filter_mask
        self._filtered_df = self.df[mask].reset_index(drop=True)
        return self._filtered_df

    def get_true_indexes(self, indexes: Iterable[int]) -> pd.Index:
        """Convert filtered row indexes to true indexes in the original data. 
        This is necessary because the view operates on the filtered data, but updates need to be applied to the original data.
        """
        indexes = pd.Index(indexes)
        if self._mask_indexes is None:
            return indexes
        return pd.Index(self._mask_indexes[indexes])

    def set_translation(self, idxs: int, text: str, level: TranslationLevel = TranslationLevel.VERIFIED):
        return self.set_translations([idxs], [text], level)

    def set_translations(
        self, idxs: Iterable[int], translations: Iterable[str]|str,
        levels: Optional[Iterable[TranslationLevel]|TranslationLevel] = TranslationLevel.VERIFIED,
        is_filtered: bool = False
    ):
        """Set translations for the given indexes.

        Arguments:
        idxs (Iterable[int]): 
            The row indexes in the filtered data for which to set translations.
        translations (Iterable[str] | str): 
            The translation(s) to set. Can be a single string for all indexes or an iterable of strings corresponding to each index.
        levels (Iterable[TranslationLevel] | TranslationLevel, optional): 
            The translation level(s) to set. Can be a single TranslationLevel for all indexes or an iterable of TranslationLevels corresponding to each index. If None, the level will not be changed. Default is TranslationLevel.VERIFIED.
        is_filtered (bool): 
            Whether the provided indexes are based on the filtered data. 
            If True, the method will convert them to true indexes in the original data before applying translations. 
            Default is False, assuming indexes are already true indexes.
        """

        # transfer idxs to mask for filtered data
        idxs = pd.Index(idxs)
        if is_filtered:
            assert self._mask_indexes is not None, "`is_filtered` is True but no filters are applied. Indexes are likely not pointing to the correct rows. Please check the logic or set `is_filtered` to False."
            # Replace the **FILTERED** data with the new translations
            idxs = self._mask_indexes[idxs]
        if idxs.empty:
            return False

        if isinstance(translations, Iterable) and not isinstance(translations, str):
            translations = pd.Series(list(translations), index=idxs)
        self.df.loc[idxs, "translation"] = translations
        if levels is None:
            pass
        elif isinstance(levels, TranslationLevel):
            self.df.loc[idxs, "level"] = levels
        elif isinstance(levels, Iterable):
            self.df.loc[idxs, "level"] = pd.Series(levels, index=idxs)

        self._filtered_df = None # Invalidate cache
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        return True

    def search_and_replace(self, filters: dict, replace_text: str, column: Literal['original', 'translation'] = "original"):
        """Replace translations based on search criteria. 
        Filters is a dict of {column: {"text": str, "is_regex": bool, "match_case": bool}}.
        Replace_text is a regex pattern or plain text to replace with. 
        Column specifies which column to apply the search and replace on if both are in the filters.
        Returns the number of replacements made.
        """
        if column not in self.df.columns:
            return 0
        mask = self.filter_mask
        if not mask.any():
            return 0
        if column == "original":
            _filter = filters.get(column, filters.get("translation", {}))
        elif column == "translation":
            _filter = filters.get(column, {})
        else:
            raise ValueError("Invalid column specified for search and replace.")

        self.df.loc[mask, "translation"] = self.df.loc[mask, column].str.replace(
            _filter.get("text", ""), replace_text, regex=_filter.get("is_regex", False),
        )
        self._filtered_df = None # Invalidate cache
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        return mask.sum()

    def apply_dictionary(self, dictionary: TranslationDictionary, keys: Optional[list[str]] = None):
        """Apply translations from the specified dictionary to the model."""
        if keys is None:
            keys = ["key"]
        # We need to be careful with set_index if keys are not unique.
        # Create copies to avoid modifying original dataframes directly until ready
        df_copy = self.df.set_index(keys)
        if (dict_df := dictionary.get(settings.TARGET_LANG)) is None:
            logger.warning(f"Dictionary does not contain target language '{settings.TARGET_LANG}'. No translations applied.")
            return
        dict_df = dict_df.set_index(keys)

        # Reindex the dictionary to match the model's index structure
        # This will fill missing entries with NaN, which we can filter out.
        dict_df = dict_df.reindex(df_copy.index)

        # Apply translations only if the level in the dictionary is higher
        mask = dict_df[f"{settings.TARGET_LANG}.level"] > df_copy["level"]

        # Update the model's data
        self.df.set_index(keys, inplace=True)
        self.df.loc[mask, "translation"] = dict_df.loc[mask, settings.TARGET_LANG]
        self.df.loc[mask, "level"] = dict_df.loc[mask, f"{settings.TARGET_LANG}.level"]
        self.df.reset_index(inplace=True)

        self._filtered_df = None # Invalidate cache
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

    def chs2cht(self):
        """Convert all Chinese translations from Simplified to Traditional using OpenCC."""
        mask = self.filter_mask
        if not mask.any():
            return
        self.df.loc[mask, "translation"] = batch_chinese_convertion(self.df.loc[mask, "translation"], target='tw')
        self._filtered_df = None
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

    def cht2chs(self):
        """Convert all Chinese translations from Traditional to Simplified using OpenCC."""
        mask = self.filter_mask
        if not mask.any():
            return
        self.df.loc[mask, "translation"] = batch_chinese_convertion(self.df.loc[mask, "translation"], target='s')
        self._filtered_df = None
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

    def is_same_original_exists(self, idxes: pd.Index|list[int]|int, is_filtered: bool = True) -> bool:
        """Checks if there are any other text units with the same original text as the given indexes. 
        This is used to determine whether to show the share translation confirmation dialog."""
        if isinstance(idxes, int):
            idxes = [idxes]
        df = self.filtered_df if is_filtered else self.df
        originals = df.iloc[idxes]["original"] if is_filtered else df.loc[idxes, "original"]
        for original in originals:
            if (self.df["original"] == original).sum() > 1:
                return True
        return False

    def get_idxs_same_original(
        self, idx: int, is_filtered: bool = True,
        max_level: TranslationLevel = TranslationLevel.UNTRANSLATED) -> pd.Index:
        """Get all indexes of text units that have the same original text as the given index."""
        if is_filtered:
            original = self.filtered_df.iloc[idx]["original"]
        else:
            original = self.df.iloc[idx]["original"]
        same_original_mask = (self.df["original"] == original) & (self.df["level"] <= max_level)
        return self.df[same_original_mask].index

    def get_first_unique_original_idxs(self, indexes: pd.Index|list[int]|int, is_filtered: bool = True) -> pd.Index:
        """Get the first unique index for each original text among the given indexes. 
        This can be used to optimize batch operations by only applying changes to one representative text unit for each unique original text."""
        if isinstance(indexes, int):
            indexes = pd.Index([indexes])
        elif isinstance(indexes, list):
            indexes = pd.Index(indexes)
        df = self.filtered_df if is_filtered else self.df
        out = df.iloc[indexes].reset_index().groupby("original").index.min()
        return pd.Index(out.values)

class TranslationCommand(QUndoCommand):
    """A command to apply a batch of changes to the DataFrame for undo/redo."""
    def __init__(
        self, model: TranslationTableModel,
        idxs: pd.Index,
        translations: Iterable[str]|str,
        levels: Optional[TranslationLevel] = None,
        description: str = "Batch Translation Edit",
    ):
        super().__init__(description)
        self.model = model
        self.idxs = idxs
        self.old = model.df.loc[idxs, "translation"].copy()
        self.old_levels = model.df.loc[idxs, "level"].copy()
        self.new = translations
        self.new_levels: Optional[pd.Series|TranslationLevel] = levels
        self.description = description
    def undo(self):
        self.model.set_translations(self.idxs, self.old, levels=self.old_levels)
        logger.debug("UNDO: Translation: %s", self.description)
    def redo(self):
        self.model.set_translations(self.idxs, self.new, levels=self.new_levels)
        logger.debug("DO: Translation: %s", self.description)

class ShareTranslationCommand(TranslationCommand):
    """A command to share a translation to all text units with the same original text."""
    def __init__(self, model: TranslationTableModel, idx: int, description: str = "Share Translation", max_level: TranslationLevel = TranslationLevel.API):
        # Get all indexes with the same original text
        same_original_idxs = model.get_idxs_same_original(idx, is_filtered=False, max_level=max_level)
        # Get the current translation to be shared
        current_translation = model.df.iloc[idx].translation
        levels = model.df.iloc[idx].level
        super().__init__(
            model=model,
            idxs=same_original_idxs,
            translations=current_translation,
            levels=levels,
            description=description
        )