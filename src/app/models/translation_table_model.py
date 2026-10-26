import logging
import pandas as pd
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence, cast, override, Optional, overload

from PySide6.QtCore import (
    Qt, QAbstractItemModel, QAbstractTableModel, QAbstractProxyModel, QSortFilterProxyModel,
    QModelIndex, QPersistentModelIndex
)
from PySide6.QtGui import QColor, QUndoCommand, QUndoStack

from app.models.filters import ColumnFilter, build_mask
from app.settings import Settings
from app.gui.dialogs.search import TableFilters
from app.gui.theme import ThemeManager
from app.locales import LanguagePack
from plugins import BaseExtractor
from core.text_unit import TextUnit
from core.translation import TranslationLevel, batch_chinese_convertion
from core.translation.dictionary import TranslationDictionary

from app.typing import IndexLikeSequence


logger = logging.getLogger(__name__)
L = LanguagePack()
class TranslationTableModel(QAbstractTableModel):
    _COLUMNS = ["file", "key", "original", "translation", "comments"]
    _HIDDEN_COLUMNS = ["level"]  # Columns that are not displayed but used for internal logic, such as translation level
    def __init__(self, data:pd.DataFrame|Sequence[TextUnit]|None=None, settings:Optional[Settings] = None, filters:Optional[TableFilters] = None, file_path: Optional[Path|str] = None, engine:Optional[BaseExtractor] = None, undo_stack: Optional[QUndoStack] = None):
        super().__init__()
        self.file_path = Path(file_path) if file_path else None
        self.engine = engine
        self.undo_stack = undo_stack
        self._in_progress_keys: set = set()  # row keys currently being translated
        cols = self._COLUMNS+self._HIDDEN_COLUMNS
        if isinstance(data, pd.DataFrame):
            self.df = data.set_index('key', drop=False)
        else:
            self.df = pd.DataFrame((u.asdict() for u in data or []), columns=cols).set_index('key', drop=False)
        self.sort(0) # Initialize order with (file, key)
        self.filters = filters if filters is not None else TableFilters(self)
        self._mask_cache: Optional[pd.Series] = None  # Cache for the current filter mask
        self.settings = settings or Settings()  # Use provided settings or default settings
        self.post_init_check()
        self.dataChanged.connect(self.update_filter_mask)  # Update the filter mask when data changes
    
    def post_init_check(self):
        if self.file_path is None:
            logger.warning("TranslationTableModel initialized without a file path. Some operations may not work (ie., loading/saving files).")
        if self.engine is None:
            logger.warning("TranslationTableModel initialized without an engine. Some operations may not work (ie., loading/saving files).")
        if self.filters is None:
            logger.warning("TranslationTableModel initialized without filters. Filters are Initialized with default empty filters, but may be disconnected from other components.")
        self.drop_duplicates(keep='last')  # Ensure no duplicate keys on initialization
        
    def drop_duplicates(self, keep:Literal['first','last']='first'):
        """Drop duplicate rows based on the 'key' column, keeping the first or last occurrence."""
        dup = self.df.duplicated(subset='key', keep=keep)
        if dup.any():
            logger.error("%s duplicate keys found. Dropping duplicates, the %s will be kept.", dup.sum(), keep)
            self.df = self.df[~dup]
            logger.warning("The following duplicate keys were dropped: \n    %s", '\n    '.join(map(str, dup[dup].keys())))
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount()-1, self.columnCount()-1))  # Emit dataChanged for the entire model
    
    def _level_from_value(self, value):
        if isinstance(value, TranslationLevel):
            return value
        if pd.isna(value):
            return TranslationLevel.UNTRANSLATED
        return TranslationLevel(value)

    # def headerData(self, section: int, orientation: PySide6.QtCore.Qt.Orientation, /, role: int = ...) -> typing.Any: ...
    @override
    def headerData(self, section:int, orientation:Qt.Orientation, /, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._COLUMNS):
                return L[self._COLUMNS[section]]
        return section + 1

    def load_units(self, units: list[TextUnit]):
        """Load a list of TextUnit objects(dataclass), and convert them into the internal DataFrame format for the model."""
        data = pd.DataFrame(units, columns=self._COLUMNS+self._HIDDEN_COLUMNS)

        self.df = pd.concat([self.df, data], ignore_index=True)
        self.drop_duplicates(keep='last')  # Ensure no duplicate keys after loading new units

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

        save_path = save_path or Path(self.settings.output_dir) / self.file_path.name
        units = self.get_units()
        self.engine.apply_translations(self.file_path, units, save_path=save_path, target_lang=self.settings.translation.target_lang)
        logger.info(f"Saved translations to {save_path}")

    @override
    def rowCount(self, /, parent:QModelIndex|QPersistentModelIndex = QModelIndex())  -> int:
        return len(self.df)
    @override
    def columnCount(self, parent:QModelIndex|QPersistentModelIndex = QModelIndex()):
        return len(self._COLUMNS)
    @override
    def data(self, index, /, role=Qt.ItemDataRole.DisplayRole):
        theme = ThemeManager.theme

        if not (
            index.isValid() and
            0<=(r:=index.row())<len(self.df) and
            0<=(c:=index.column())<len(self._COLUMNS)
        ):
            return None

        if ((role == Qt.ItemDataRole.BackgroundRole and theme.USE_COLOR_LEVEL_BACKGROUND) or
            (role == Qt.ItemDataRole.ForegroundRole and not theme.USE_COLOR_LEVEL_BACKGROUND) ):
            level = self._level_from_value(self.df.iloc[r]['level'])
            return QColor(ThemeManager.theme.get_level_color(level))

        # value = self.df.iat[r, c] # this will break if the column order changes, so we use the column name instead
        value = self.df.iloc[r][self._COLUMNS[c]]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole) and not pd.isna(value):
            return str(value)
        return None

    @override
    def setData(self, index, value, /, role=Qt.ItemDataRole.EditRole):
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
            # TODO: maybe we want it to be handled by the TranslationSession?
            self.undo_stack.beginMacro("Inline Edit Translation")
            self.undo_stack.push(TranslationCommand(
                model=self,
                idxs=self.df.index[[r]],
                translations=[text],
                levels=level,
                description=f"Inline Edit"
            ))
            _idx = self.df.index[r]
            self.undo_stack.push(ShareTranslationCommand(
                self, self.df.index[r], description=f"Share Translation for index: {_idx}",
                max_level=TranslationLevel.VERIFIED
            ))
            self.undo_stack.endMacro()
        else:
            self.set_translations(self.df.index[[r]], [text], levels=level)
        return True
    
    @override
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        # make items selectable and enabled; only the Translation column is editable
        col = index.column()
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        try:
            if self._COLUMNS[col] == "translation":
                flags |= Qt.ItemFlag.ItemIsEditable
        except Exception:
            pass
        return flags

    @property
    def filter_mask(self) -> pd.Series:
        if self._mask_cache is None:
            self._mask_cache=self.filters.build_mask(self.df)
        return self._mask_cache
    
    def _update_filter_mask_cache(self, rows: pd.Index|list[int]):
        """
        Arguments:
            rows (pd.Index[int] | list[int]): The int row indexes in the DataFrame for which to update the filter mask.
        """
        if self._mask_cache is None: # No cached mask to update
            return # it will be recalculated on next access
        else:
            new_mask = self.filters.build_mask(self.df.iloc[rows]) # integer indexes not keys
            self._mask_cache.iloc[rows] = new_mask
            
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
        self, idxs: IndexLikeSequence, translations: Iterable[str]|str,
        levels: Optional[Iterable[TranslationLevel]|TranslationLevel] = TranslationLevel.VERIFIED
    ):
        """Set translations for the given indexes.

        Arguments:
            idxs (IndexLike): 
                The row indexes in the filtered data for which to set translations.
            translations (Iterable[str] | str): 
                The translation(s) to set. Can be a single string for all indexes or an iterable of strings corresponding to each index.
            levels (Iterable[TranslationLevel] | TranslationLevel, optional): 
                The translation level(s) to set. Can be a single TranslationLevel for all indexes or an iterable of TranslationLevels corresponding to each index. If None, the level will not be changed. Default is TranslationLevel.VERIFIED.
        """
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
        self.emit_df_row_changed(idxs)
        return True
    
    def emit_df_row_changed(self, idxs: pd.Index|pd.Series):
        """Emit dataChanged signal for the specific rows that were updated in the DataFrame."""
        if isinstance(idxs, pd.Series):
            idxs = idxs[idxs].index  # Get the index of True values
        if idxs.empty:
            return 0
        int_idxs = self.df.index.get_indexer(idxs)
        self.dataChanged.emit(self.index(int_idxs.min().astype(int), 0), self.index(int_idxs.max().astype(int), self.columnCount() - 1))
        return len(int_idxs)
    
    def search_and_replace(self, filters: dict[Literal['file', 'key', 'original', 'translation'], ColumnFilter], replace_text: str, column: Literal['original', 'translation'] = "original"):
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
        elif (_filter := filters.get(column)) is None:
            logger.error(f"Column '{column}' not found in provided filters. Cannot perform search and replace.")
            return 0
        # TODO: Add a option to ignore the level filter under search&replace.
        mask = build_mask(self.df, filters=filters.values(), levels=[lv for lv, show in self.filters.levels.items() if show])
        if not mask.any():
            logger.info("No rows matched the search criteria. No replacements made.")
            return 0
        self.df.loc[mask, "translation"] = self.df.loc[mask, column].str.replace(
            _filter.text, replace_text, regex=_filter.is_regex, case=_filter.match_case
        )
        return self.emit_df_row_changed(mask)

    def apply_dictionary(self, dictionary: TranslationDictionary, keys: Optional[list[str]] = None) -> None:
        keys = keys or ["key"]
        if (dict_df := dictionary.get(self.settings.translation.target_lang)) is None:
            logger.warning(f"Dictionary does not contain target language '{self.settings.translation.target_lang}'. No translations applied.")
            return
        level_col = f"{self.settings.translation.target_lang}.level"
        if keys!=["key"]: 
            # self.df is indexed by 'key'. We need to align them based on the specified keys.
            df = self.df.set_index(keys)
            dict_unique = dict_df.drop_duplicates(keys,keep='last').set_index(keys)
            dict_aligned = dict_unique.reindex(df.index)
            mask = dict_aligned[level_col] > df["level"]
            if not mask.any():
                return
            df.loc[mask, "translation"] = dict_aligned.loc[mask, self.settings.translation.target_lang]
            df.loc[mask, "level"] = dict_aligned.loc[mask, level_col]
            self.df = df.reset_index().set_index('key', drop=False)
            updated_keys = self.df.index[mask]
        else:
            # Invariant: self.df is always indexed by `keys` with drop=False.
            dict_aligned = dict_df.set_index(keys).reindex(self.df.index)

            mask = dict_aligned[level_col] > self.df["level"]
            if not mask.any():
                return

            updated_keys = self.df.index[mask]

            self.df.loc[mask, "translation"] = dict_aligned.loc[mask, self.settings.translation.target_lang]
            self.df.loc[mask, "level"] = dict_aligned.loc[mask, level_col]

        if diff_comments := dictionary.check_difference(self.df, self_type="old"):
            comments = pd.Series(diff_comments)
            comments.index.name = self.df.index.name
            self.df["comments"] = comments.reindex(self.df.index)

        self.emit_df_row_changed(updated_keys)

    def chinese_convertion(self, target: Literal['s','t'], max_level: TranslationLevel = TranslationLevel.LOCKED):
        """Convert all Chinese translations between Simplified and Traditional using OpenCC."""
        mask = self.filter_mask & (self.df["level"] <= max_level)
        if (idxs:= self.df.index[mask]).empty:
            return
        self.df.loc[mask, "translation"] = batch_chinese_convertion(self.df.loc[mask, "translation"], target)
        self.emit_df_row_changed(idxs)
        
    def share_top_lv_translations(self, max_level: TranslationLevel = TranslationLevel.VERIFIED):
        """Share the translation of the given indexes to all other text units with the same original text, if the translation level is higher than the existing ones."""
        # get the df sorted by original,level
        df_sorted = self.df.sort_values(["original", "level"], )
        # drop duplicates based on original, keeping the highest level translation
        df_top_unique = df_sorted.drop_duplicates(subset="original", keep="last")
        # Push share translation command:
        df_candidates = self.df[self.df["level"] < max_level].set_index('original')
        df_aligned = df_top_unique.set_index('original').reindex(df_candidates.index, fill_value=None)
        mask = df_aligned["level"] > df_candidates["level"]
        if not mask.any():
            logger.info("No translations to share: no higher level translations found.")
            return
        idxs_to_update = pd.Index(df_candidates[mask].key)
        translations_to_update = df_aligned.loc[mask, "translation"]
        levels_to_update = df_aligned.loc[mask, "level"]
        if self.undo_stack is not None:
            self.undo_stack.push(TranslationCommand(
                model=self,
                idxs=idxs_to_update,
                translations=translations_to_update,
                levels=levels_to_update,
                description=f"Share Top Level Translations (max_level={max_level.name})"
            ))
        else:
            self.set_translations(idxs_to_update, translations_to_update, levels_to_update)
        
    def is_same_original_exists(self, idxs: IndexLikeSequence|int) -> bool:
        """Checks if there are any other text units with the same original text as the given indexes. 
        This is used to determine whether to show the share translation confirmation dialog."""
        if isinstance(idxs, int):
            original = self.df.iloc[idxs]["original"]
            return (self.df["original"] == original).sum() > 1
        elif not isinstance(idxs, (list, pd.Index, pd.Series, list)):
            idxs = pd.Index(idxs)
        originals = self.df.loc[idxs, "original"]
        return any((self.df["original"] == original).sum() > 1 for original in originals)

    def get_idxs_same_original(
        self, idx: int|str, is_filtered: bool = True,
        max_level: TranslationLevel = TranslationLevel.UNTRANSLATED) -> pd.Index:
        """Get all indexes of text units that have the same original text as the given index."""
        if is_filtered:
            original = self.df.loc[idx, "original"]
        else:
            original = self.df.loc[idx, "original"]
        same_original_mask = (self.df["original"] == original) & (self.df["level"] <= max_level)
        return self.df[same_original_mask].index

    # def get_first_unique_original_idxs(self, indexes: pd.Index|list[int]|int, is_filtered: bool = True) -> pd.Index:
    #     """Get the first unique index for each original text among the given indexes. 
    #     This can be used to optimize batch operations by only applying changes to one representative text unit for each unique original text."""
    #     # TODO: This is unused and might be deprecated
    #     df = self.df if is_filtered else self.df
    #     out = df.iloc[indexes].reset_index().groupby("original").index.min()
    #     return pd.Index(out.values)
    
    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        if not (0 <= column < len(self._COLUMNS)):
            return

        self.layoutAboutToBeChanged.emit()
        
        col_name = self._COLUMNS[column]
        ascending = (order == Qt.SortOrder.AscendingOrder)
        
        # Fast vector sorting using pandas string methods
        # Use key to perform case-insensitive sort without altering actual data
        if col_name == 'key':
            self.df.sort_index(ascending=ascending, inplace=True, ignore_index=False)
        else:
            self.df.sort_values(
                by=(col_name),
                ascending=ascending,
                inplace=True,
                key=lambda col: col.astype(str).str.casefold(),
                ignore_index=False # keep the index
            )
        
        # Clear filter mask cache since index order changed
        self.clear_filter_mask()

        self.layoutChanged.emit()

class TranslationTableProxyModel(QSortFilterProxyModel):
    """A proxy model for the TranslationTableModel to support sorting and filtering in the view."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDynamicSortFilter(True)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._accepted_rows: Optional[set[int]] = None  # Cache of accepted source model rows for fast filtering
    
    @override
    def setSourceModel(self, sourceModel: QAbstractItemModel) -> None:
        """
        Arguments:
            sourceModel (TranslationTableModel): The source model to be set for this proxy model. Must be an instance of TranslationTableModel.
        """
        assert isinstance(sourceModel, TranslationTableModel)
        super().setSourceModel(sourceModel)
        
    def set_translation_table_model(self, model: TranslationTableModel):
        """Set the source model for this proxy model. This is a convenience method to ensure type safety."""
        self.setSourceModel(model)
        self.filters = model.filters  # Bind the filters from the source model to the proxy model
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
        self._accepted_rows = None  # Clear the cache of accepted rows
        super().invalidateFilter()  # Trigger re-evaluation of filterAcceptsRow

    @override
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex|QPersistentModelIndex, /)->bool:
        if not self.sourceModel().filters.is_filtering:
            return True
        df_index = self.sourceModel().df.index[source_row]
        return df_index in self.accepted_rows
    
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
    
    @override
    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        # Delegate sorting directly to the pandas-backed source model
        if self.sourceModel():
            self.sourceModel().sort(column, order)

class TranslationCommand(QUndoCommand):
    """A command to apply a batch of changes to the DataFrame for undo/redo."""
    def __init__(
        self, model: TranslationTableModel,
        idxs: IndexLikeSequence,
        translations: Iterable[str]|str,
        levels:  Optional[Iterable[TranslationLevel]|TranslationLevel] = None,
        description: str = "Batch Translation Edit",
    ):
        super().__init__(description)
        self.model = model
        self.idxs = idxs
        self.old = model.df.loc[idxs]["translation"].copy()
        self.old_levels = model.df.loc[idxs]["level"].copy()
        self.new = translations
        self.new_levels: Optional[Iterable[TranslationLevel]|TranslationLevel] = levels
        self.description = description
    def undo(self):
        self.model.set_translations(self.idxs, self.old, levels=self.old_levels)
        logger.debug("UNDO: Translation: %s", self.description)
    def redo(self):
        self.model.set_translations(self.idxs, self.new, levels=self.new_levels)
        logger.debug("DO: Translation: %s", self.description)

class ShareTranslationCommand(TranslationCommand):
    """A command to share a translation to all text units with the same original text."""
    def __init__(self, model: TranslationTableModel, idx: int|str, description: str = "Share Translation", max_level: TranslationLevel = TranslationLevel.API):
        # Get all indexes with the same original text
        same_original_idxs = model.get_idxs_same_original(idx, is_filtered=False, max_level=max_level)
        # Get the current translation to be shared
        current_translation = model.df.loc[idx]['translation']
        levels = TranslationLevel(model.df.loc[idx]['level'])
        super().__init__(
            model=model,
            idxs=same_original_idxs,
            translations=current_translation,
            levels=levels,
            description=description
        )

@overload
def get_source_indexes(model:QAbstractProxyModel, proxy_indexes: Iterable[QModelIndex], dtype: type[QModelIndex]) -> list[QModelIndex]: ...
@overload
def get_source_indexes(model:QAbstractProxyModel, proxy_indexes: Iterable[QModelIndex], dtype: type[int]) -> list[int]: ...
@overload
def get_source_indexes(model:QAbstractProxyModel, proxy_indexes: Iterable[QModelIndex], dtype: type[pd.Index]) -> pd.Index: ...
def get_source_indexes(model:QAbstractProxyModel, proxy_indexes: Iterable[QModelIndex], dtype: type = QModelIndex) -> list[QModelIndex]|list[int]|pd.Index:
    """Convert a list of proxy indexes to the corresponding source model indexes or row numbers."""
    if dtype == QModelIndex:
        return [model.mapToSource(idx) for idx in proxy_indexes]
    elif dtype == int:
        return [model.mapToSource(idx).row() for idx in proxy_indexes]
    elif dtype == pd.Index:
        return pd.Index([model.mapToSource(idx).row() for idx in proxy_indexes])
    raise ValueError(f"Unsupported dtype: {dtype}. Must be QModelIndex, int, or pd.Index.")