


import logging
import pandas as pd
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence, cast, override, Optional, overload

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QUndoCommand, QUndoStack

from app.models.filters import ColumnFilter, build_mask
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
    _COLUMNS = ["file", "key", "original", "translation", "comments"]
    _HIDDEN_COLUMNS = ["level"]  # Columns that are not displayed but used for internal logic, such as translation level
    
    def __init__(self, data=None, filters:Optional[TableFilters] = None, file_path: Optional[Path|str] = None, engine:Optional[BaseExtractor] = None, undo_stack: Optional[QUndoStack] = None):
        super().__init__()
        self.file_path = Path(file_path) if file_path else None
        self.engine = engine
        self.undo_stack = undo_stack
        self.df:pd.DataFrame = pd.DataFrame(data or [], columns=self._COLUMNS+self._HIDDEN_COLUMNS)
        self.filters = filters if filters is not None else TableFilters(self)
        self._mask_cache: Optional[pd.Series] = None  # Cache for the current filter mask
        
        self.dataChanged.connect(self.update_filter_mask)  # Update the filter mask when data changes
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
        return len(self.df)
    @override
    def columnCount(self, parent=QModelIndex()):
        return len(self._COLUMNS)
    @override
    def data(self, index, role=Qt.DisplayRole):
        theme = ThemeManager.theme

        if not (
            index.isValid() and
            0<=(r:=index.row())<len(self.df) and
            0<=(c:=index.column())<len(self._COLUMNS)
        ):
            return None
        row, col = self.df.iloc[r], self._COLUMNS[c]

        if ((role == Qt.BackgroundRole and theme.USE_COLOR_LEVEL_BACKGROUND) or
            (role == Qt.ForegroundRole and not theme.USE_COLOR_LEVEL_BACKGROUND) ):
            level = self._level_from_value(row.level)
            return QColor(ThemeManager.theme.get_level_color(level))

        if role in (Qt.DisplayRole, Qt.EditRole):
            if col =='key':
                return str(row.get(col, ""))
            return row.get(col, "")
        return None

    @override
    def setData(self, index, value, role=Qt.EditRole):
        # Support inline editing from the view for the Translation column
        if not (
            index.isValid() and
            0<=(r:=index.row())<len(self.df) and
            0<=(c:=index.column())<len(self._COLUMNS)
        ):
            return False
        try:
            if self._COLUMNS[c] != "translation":
                return False
        except Exception:
            logger.error(f"Invalid column index {c} for setData.")
            return False
        text = str(value)
        original = self.df.iloc[r].get("original")
        if original is None:
            return False
        
        level = TranslationLevel.VERIFIED if text else TranslationLevel.UNTRANSLATED
        
        if self.undo_stack is not None: # if not connected to a session's undo stack, apply changes directly without undo support
            self.undo_stack.push(TranslationCommand(
                model=self,
                idxs=[r],
                translations=[text],
                levels=level,
                description=f"Inline Edit"
            ))
        else:
            self.set_translations([r], [text], levels=level)
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

    @property
    def filter_mask(self) -> pd.Series:
        if self._mask_cache is None:
            self._mask_cache=self.filters.build_mask(self.df)
        return self._mask_cache
    
    def _update_filter_mask_cache(self, rows: pd.Index|list[int]):
        if self._mask_cache is None: # No cached mask to update
            return # it will be recalculated on next access
        else:
            new_mask = self.filters.build_mask(self.df.loc[rows])
            self._mask_cache.loc[rows] = new_mask
            
    def update_filter_mask(self, start_index: QModelIndex, end_index: QModelIndex, roles: Sequence[int] = []):
        """Recaculate and update the mask at the given indexes,
        This should be called if specific rows are updated to prevent full recalculation of the mask
        """
        rows = pd.Index(range(start_index.row(), end_index.row() + 1))
        logger.debug("Updating filter mask for %d rows: %d to %d", len(rows), start_index.row(), end_index.row())
        self._update_filter_mask_cache(rows)

    def clear_filter_mask(self, *args, **kwargs):
        """Clear the cached filter mask to force recalculation on next access. 
        This should be called whenever the filters changes"""
        self._mask_cache = None

    def set_translation(self, idxs: int, text: str, level: TranslationLevel = TranslationLevel.VERIFIED):
        return self.set_translations([idxs], [text], level)

    def set_translations(
        self, idxs: Iterable[int], translations: Iterable[str]|str,
        levels: Optional[Iterable[TranslationLevel]|TranslationLevel] = TranslationLevel.VERIFIED
    ):
        """Set translations for the given indexes.

        Arguments:
        idxs (Iterable[int]): 
            The row indexes in the filtered data for which to set translations.
        translations (Iterable[str] | str): 
            The translation(s) to set. Can be a single string for all indexes or an iterable of strings corresponding to each index.
        levels (Iterable[TranslationLevel] | TranslationLevel, optional): 
            The translation level(s) to set. Can be a single TranslationLevel for all indexes or an iterable of TranslationLevels corresponding to each index. If None, the level will not be changed. Default is TranslationLevel.VERIFIED.
        """
        if not isinstance(idxs, pd.Index):
            idxs = pd.Index(idxs)
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
            self.df.loc[idxs, "level"] = pd.Series(list(levels), index=idxs)
        else:
            logger.error(f"Invalid type for levels: {type(levels)}. Must be TranslationLevel or Iterable[TranslationLevel].")
        # Emit dataChanged signal for the specific rows that were updated
        self.dataChanged.emit(self.index(idxs.min(), 0), self.index(idxs.max(), self.columnCount() - 1))
        return True

    def search_and_replace(self, filters: list[ColumnFilter], replace_text: str, column: Literal['original', 'translation'] = "original"):
        """Replace translations based on search criteria. 
        Replace_text is a regex pattern or plain text to replace with. 
        Column specifies which column to apply the search and replace on if both are in the filters.
        Returns the number of replacements made.
        """
        if column not in self.df.columns:
            logger.error(f"Column '{column}' not found in DataFrame. Cannot perform search and replace.")
            return 0
        if not filters:
            logger.warning("No filters provided for search and replace. No replacements made.")
            return 0
        # TODO: Add a option to ignore the level filter under search&replace.
        mask = build_mask(self.df, filters=filters, levels=[lv for lv, show in self.filters.levels.items() if show])
        if not mask.any():
            logger.info("No rows matched the search criteria. No replacements made.")
            return 0
        for _filter in filters:
            # Prioritizes Translation column if multiple filters are provided.
            #TODO: consider allowing the user to specify which column to prioritize or apply the replace on.
            if _filter.column == 'translation':
                break
        self.df.loc[mask, "translation"] = self.df.loc[mask, column].str.replace(
            _filter.text, replace_text, regex=_filter.is_regex, case=_filter.match_case
        )
        if (idxs := self.df.index[mask]).empty:
            return 0
        self.dataChanged.emit(self.index(idxs.min(), 0), self.index(idxs.max(), self.columnCount() - 1))
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
        if (idxs := self.df.index[mask]).empty:
            return # No translations to apply
        # Update the model's data
        self.df.set_index(keys, inplace=True)
        self.df.loc[mask, "translation"] = dict_df.loc[mask, settings.TARGET_LANG]
        self.df.loc[mask, "level"] = dict_df.loc[mask, f"{settings.TARGET_LANG}.level"]
        self.df.reset_index(inplace=True)
        if diff_comments := dictionary.check_difference(self.df, self_type="old"):
            labels_df = pd.DataFrame(list(diff_comments.items()), columns=["key", "comments"])
            self.df = self.df.merge(labels_df, on="key", how="left")
        self.dataChanged.emit(self.index(idxs.min(), 0), self.index(idxs.max(), self.columnCount() - 1))

    def chinese_convertion(self, target: Literal['s','t']):
        """Convert all Chinese translations between Simplified and Traditional using OpenCC."""
        mask = self.filter_mask
        if (idxs:= self.df.index[mask]).empty:
            return
        self.df.loc[mask, "translation"] = batch_chinese_convertion(self.df.loc[mask, "translation"], target)
        self.dataChanged.emit(self.index(idxs.min(), 0), self.index(idxs.max(), self.columnCount() - 1))

    def chs2cht(self): return self.chinese_convertion(target='t')
    def cht2chs(self): return self.chinese_convertion(target='s')
        
    def is_same_original_exists(self, idxes: pd.Index|list[int]|int, is_filtered: bool = True) -> bool:
        """Checks if there are any other text units with the same original text as the given indexes. 
        This is used to determine whether to show the share translation confirmation dialog."""
        if isinstance(idxes, int):
            idxes = [idxes]
        df = self.df if is_filtered else self.df
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
            original = self.df.iloc[idx]["original"]
        else:
            original = self.df.iloc[idx]["original"]
        same_original_mask = (self.df["original"] == original) & (self.df["level"] <= max_level)
        return self.df[same_original_mask].index

    def get_first_unique_original_idxs(self, indexes: pd.Index|list[int]|int, is_filtered: bool = True) -> pd.Index:
        """Get the first unique index for each original text among the given indexes. 
        This can be used to optimize batch operations by only applying changes to one representative text unit for each unique original text."""
        df = self.df if is_filtered else self.df
        out = df.iloc[indexes].reset_index().groupby("original").index.min()
        return pd.Index(out.values)

class CaseInsensitiveSortProxyModel(QSortFilterProxyModel):
    def lessThan(self, left_index, right_index):
        # Retrieve display values for comparison
        left_data = self.sourceModel().data(left_index, Qt.DisplayRole)
        right_data = self.sourceModel().data(right_index, Qt.DisplayRole)
        
        # Convert to string and lowercase for case-insensitive comparison
        left_str = str(left_data).lower() if left_data is not None else ""
        right_str = str(right_data).lower() if right_data is not None else ""
        
        return left_str < right_str


class TranslationTableProxyModel(CaseInsensitiveSortProxyModel):
    """A proxy model for the TranslationTableModel to support sorting and filtering in the view."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDynamicSortFilter(True)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._accepted_rows: Optional[set[int]] = None  # Cache of accepted source model rows for fast filtering
    
    @override
    def setSourceModel(self, sourceModel: TranslationTableModel) -> None:
        assert isinstance(sourceModel, TranslationTableModel)
        super().setSourceModel(sourceModel)
        self.filters = sourceModel.filters  # Bind the filters from the source model to the proxy model
        self.filters.text_filter_changed.connect(self.invalidateFilter)
        self.filters.level_filter_changed.connect(self.invalidateFilter)

    @override
    def sourceModel(self) -> TranslationTableModel:
        source = super().sourceModel()
        assert isinstance(source, TranslationTableModel)
        return source
        
    @override
    def invalidateFilter(self, *args, **kwargs):
        self.sourceModel().clear_filter_mask()
        super().invalidateFilter()  # Trigger re-evaluation of filterAcceptsRow

    @override
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self.sourceModel().filters.is_filtering:
            return True
        return source_row in self.accepted_rows
    
    @property
    def accepted_rows(self) -> set[int]:
        """Return the set of source model row indexes that are currently accepted by the filters."""
        if self._accepted_rows is None:
            mask = self.sourceModel().filter_mask
            self._accepted_rows = set(mask[mask].index)
        return self._accepted_rows
    
    def get_true_index(self, proxy_index: QModelIndex) -> QModelIndex:
        """Convert a proxy index to the corresponding source model index."""
        if not proxy_index.isValid():
            return QModelIndex()
        return self.mapToSource(proxy_index)
    @overload
    def get_true_indexes(self, proxy_indexes: Iterable[QModelIndex], dtype: type[QModelIndex]) -> list[QModelIndex]: ...
    @overload
    def get_true_indexes(self, proxy_indexes: Iterable[QModelIndex], dtype: type[int]) -> list[int]: ...
    @overload
    def get_true_indexes(self, proxy_indexes: Iterable[QModelIndex], dtype: type[pd.Index]) -> pd.Index: ...
    def get_true_indexes(self, proxy_indexes: Iterable[QModelIndex], dtype: type = QModelIndex) -> list[QModelIndex]|list[int]|pd.Index:
        """Convert a list of proxy indexes to the corresponding source model indexes or row numbers."""
        if dtype == QModelIndex:
            return [self.mapToSource(idx) for idx in proxy_indexes]
        elif dtype == int:
            return [self.mapToSource(idx).row() for idx in proxy_indexes]
        elif dtype == pd.Index:
            return pd.Index([self.mapToSource(idx).row() for idx in proxy_indexes])
        raise ValueError(f"Unsupported dtype: {dtype}. Must be QModelIndex, int, or pd.Index.")

class TranslationCommand(QUndoCommand):
    """A command to apply a batch of changes to the DataFrame for undo/redo."""
    def __init__(
        self, model: TranslationTableModel,
        idxs: pd.Index|list[int],
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
        levels = TranslationLevel(model.df.iloc[idx].level)
        super().__init__(
            model=model,
            idxs=same_original_idxs,
            translations=current_translation,
            levels=levels,
            description=description
        )