import logging
import pandas as pd
from typing import Iterable, Optional, overload, Literal
from dataclasses import dataclass
from PyQt5.QtCore import QObject

from qt_utils import TypedQtSignal
from core.translation import TranslationLevel

logger = logging.getLogger(__name__)

@dataclass
class ColumnFilter:
    column: str
    text: str
    is_regex: bool = False
    match_case: bool = False

    def mask(self, data:pd.Series|pd.DataFrame) -> pd.Series:
        """Returns a boolean mask for the given pandas Series based on the filter criteria."""
        if isinstance(data, pd.DataFrame):
            if self.column not in data.columns:
                raise ValueError(f"Column '{self.column}' not found in DataFrame.")
            series = data[self.column]
        else:
            series = data
        series = series.astype(str) # ensure strings
        mask = series.str.contains(self.text, case=self.match_case, regex=self.is_regex, na=False)
        return mask
    
    def __bool__(self):
        return bool(self.text)  # A filter is considered active if it has non-empty text

class TableFilters(QObject):
    text_filter_changed = TypedQtSignal()
    level_filter_changed = TypedQtSignal(list)
    def __init__(self, parent:Optional[QObject]=None):
        super().__init__(parent)
        self.levels = {lv:True for lv in TranslationLevel}  # Keep track of which translation levels are currently selected for filtering
        self.filters: dict[str, ColumnFilter] = {}
        
    def __repr__(self):
        return f"TableFilters(levels={list(self.levels.values())}, filters={self.filters})"
    def build_mask(self, df: pd.DataFrame):
        logger.debug(f"Building mask for DataFrame with {len(df)} rows using filters: {self.filters} and levels: {self.levels}")
        return build_mask(df, filters=self.filters.values(), levels=[lv for lv, show in self.levels.items() if show])
    
    def filter(self, df:pd.DataFrame):
        mask = self.build_mask(df)
        return df[mask].reset_index(drop=True)
    
    @property
    def is_filtering(self):
        return not all(self.levels.values()) or any(self.filters.values())
    
    @overload
    def get(self, column:Literal['level']) -> list[TranslationLevel]:
        ...
    @overload
    def get(self, column:str) -> ColumnFilter|None:
        ...
    def get(self, column:str) -> ColumnFilter|list[TranslationLevel]|None:
        if column == "level":
            return [lv for lv, show in self.levels.items() if show]
        return self.filters.get(column)

    def set_filters(self, filters:list[ColumnFilter]):
        self.filters.clear() # Clear old filters first
        for filt in filters:
            self.filters[filt.column] = filt
        self.text_filter_changed.emit()
        
    def set_filter(self, column:str, text:str, is_regex:bool=False, match_case:bool=False):
        self.filters[column] = ColumnFilter(column, text, is_regex, match_case)
        self.text_filter_changed.emit()

    def set_level(self, levels:list[TranslationLevel], checked:bool):
        for level in levels:
            self.levels[level] = checked
        self.level_filter_changed.emit(levels)
    
def build_mask(df: pd.DataFrame, filters: Optional[Iterable[ColumnFilter]], levels: Optional[list[TranslationLevel]]) -> pd.Series:
    """Builds a boolean mask for the DataFrame based on the provided filters and translation levels."""
    if filters is None and levels is None:
        logger.warning("No filters or levels provided to build_mask; returning all True mask.")
    elif levels is not None:
        level_shown = set(levels)
        mask = df['level'].isin(level_shown)  # Use isin for better performance and correctness
    else:
        mask = pd.Series(True, index=df.index)  # Return all True if no filters or
    if filters is not None:
        for filt in filters:
            if filt.column not in df.columns:
                continue
            mask &= filt.mask(df)
    return mask