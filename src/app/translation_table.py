import pandas as pd
import logging
from pathlib import Path
from typing import Iterable, Optional, Any, cast

from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QAbstractTableModel
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QTabWidget, QTableView, QAbstractItemView, QCheckBox,
    QInputDialog, QMenu, QApplication, QUndoCommand, QUndoStack
)
from iod import IndexedOrderedDict
from config import settings
from core.text_unit import TextUnit
from core.translation import TranslationLevel, TranslationDictionary, Translator, batch_chinese_convertion
from .language import LanguagePack
from .gui.theme import ThemeManager

logger = logging.getLogger(__name__)
L = LanguagePack()

class TranslationTableModel(QAbstractTableModel):
    _columns = ["file", "id", "attribute", "original", "translation"]
    _HIDDEN_COLUMNS = ["json_path", "level"]  # Columns that are not displayed but used for internal logic, such as translation level
    # translation_changed = pyqtSignal(list[int], list[str], TranslationLevel|None)  # row index, new translation text, level
    def __init__(self, data=None, file_path: Optional[Path|str] = None, engine = None):
        super().__init__()
        self.file_path = Path(file_path) if file_path else None
        self.engine = engine
        self.df:pd.DataFrame = pd.DataFrame(data or [], columns=self._columns+self._HIDDEN_COLUMNS)
        self._filtered_df = None
        self.filters = {}
        self._mask_indexes = None
        # self._ensure_level_defaults()

    def _level_from_value(self, value):
        if isinstance(value, TranslationLevel):
            return value
        if pd.isna(value):
            return TranslationLevel.UNTRANSLATED
        return TranslationLevel(value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return L[self._columns[section]]
        return section + 1
    
    def load_units(self, units: list[TextUnit]):
        """Load a list of TextUnit objects(dataclass), and convert them into the internal DataFrame format for the model."""
        data = pd.DataFrame(units, columns=self._columns+self._HIDDEN_COLUMNS)
        
        self.df = pd.concat([self.df, data], ignore_index=True)
        self.set_filters(self.filters)  # Re-apply filters to include new data

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

    def save_to_game_file(self, save_path: Optional[Path|str] = None):
        """Apply translations back to the game file using the bound engine."""
        if not self.file_path or not self.engine:
            logger.error("Cannot save: file_path or engine not set.")
            return
        
        save_path = save_path or Path(settings.output_dir) / self.file_path.name
        units = self.get_units()
        self.engine.apply_translations(self.file_path, units, save_path=save_path)
        logger.info(f"Saved translations to {save_path}")

    def set_filters(self, filters):
        # filters: dict of {column: {"text": str, "is_regex": bool}}
        self.filters = filters or {}
        # clear cached filtered data so it will be recalculated
        self._mask_indexes = None
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return len(self.filtered_df)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def build_mask(self, filters):
        # Build boolean mask for all filters (case-insensitive substring match)
        mask = pd.Series([True] * len(self.df), index=self.df.index)
        for col, filterdf in filters.items():
            if col not in self.df.columns:
                continue
            text = filterdf.get("text", "")
            is_regex = filterdf.get("is_regex", False)
            # ensure strings and perform case-insensitive substring match
            mask &= self.df[col].astype(str).str.contains(text, case=False, regex=is_regex, na=False)
        self._mask_indexes = mask[mask].index
        return mask
        
    @property
    def filtered_df(self):
        if not self.filters:
            return self.df
        if self._mask_indexes is not None:
            return self.df.loc[self._mask_indexes].reset_index(drop=True)
        mask = self.build_mask(self.filters)
        return self.df[mask].reset_index(drop=True)

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
            if c < 0 or c >= len(self._columns):
                return None
            row = self.filtered_df.iloc[r]
            col = self._columns[c]
            return row.get(col, "")
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        # make items selectable and enabled; only the Translation column is editable
        col = index.column()
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        try:
            if self._columns[col] == "translation":
                flags |= Qt.ItemIsEditable
        except Exception:
            pass
        return flags
    
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
            return True
        elif isinstance(levels, TranslationLevel):
            self.df.loc[idxs, "level"] = levels
        elif isinstance(levels, Iterable):
            self.df.loc[idxs, "level"] = pd.Series(levels, index=idxs)
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        return True
        
    def search_and_replace(self, filters: dict, replace_text: str, column: str = "original"):
        """Replace translations based on search criteria. 
        Filters is a dict of {column: {"text": str, "is_regex": bool, "match_case": bool}}.
        Replace_text is a regex pattern or plain text to replace with. Column specifies which column to apply the search and replace on (default "original").
        Returns the number of replacements made.
        """
        if column not in self.df.columns:
            return 0
        mask = self.build_mask(filters)
        if not mask.any():
            return 0
        self.df.loc[mask, "translation"] = self.df.loc[mask, column].str.replace(
            filters[column]["text"], replace_text, regex=filters[column].get("is_regex", False),
        )
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        return mask.sum()
        
    def setData(self, index, value, role=Qt.EditRole):
        # Support inline editing from the view for the Translation column
        if role != Qt.EditRole or not index.isValid():
            return False
        row = index.row()
        col = index.column()
        try:
            col_name = self._columns[col]
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
        self.set_translations(idx, [text], levels=TranslationLevel.VERIFIED if text else TranslationLevel.UNTRANSLATED)
        
        return True
    
    def apply_dictionary(self, dictionary: TranslationDictionary, keys: Optional[list[str]] = None):
        """Apply translations from the specified dictionary to the model."""
        if keys is None:
            keys = ["json_path", "original"]
        
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
        
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        
    def chs2cht(self):
        """Convert all Chinese translations from Simplified to Traditional using OpenCC."""
        filtered = self.filtered_df
        if filtered.empty:
            return 
        filtered["translation"] = batch_chinese_convertion(filtered["translation"], target='tw')
        
    def cht2chs(self):
        """Convert all Chinese translations from Simplified to Traditional using OpenCC."""
        filtered = self.filtered_df
        if filtered.empty:
            return
        filtered["translation"] = batch_chinese_convertion(filtered["translation"], target='s')
    
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

class TranslationTableView(QTableView):
    _COLWIDTHS = [60, 20, 80, 500, 500]
    def __init__(self, parent=None):
        super().__init__(parent)
        # Use row selection and single selection so a row is selected at a time
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # self.setAlternatingRowColors(True)
        # enable custom context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # allow inline editing via double-click or edit key
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked | 
            QAbstractItemView.EditKeyPressed | # F2
            QAbstractItemView.SelectedClicked  #
        ) 
        self.translator = Translator(settings)
        # horizontal header left align and stretch last section
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.horizontalHeader().setStretchLastSection(True)

        self.history = QUndoStack()
        self.undo_action = self.history.createUndoAction(self, "Undo")
        self.undo_action.setShortcuts(QKeySequence.Undo)   # Ctrl+Z / Cmd+Z
        self.redo_action = self.history.createRedoAction(self, "Redo")
        self.redo_action.setShortcuts(QKeySequence.Redo)   # Ctrl+Y / Cmd+Shift+Z
        self.addAction(self.undo_action)
        self.addAction(self.redo_action)
        
    def setModel(self, model):
        super().setModel(model)
        self.set_column_widths(self._COLWIDTHS)
        
    def set_column_widths(self, colwidths: list[int]):
        for i, width in enumerate(colwidths):
            self.setColumnWidth(i, width)
            
    def edit_translation_row(self, row: int, model: TranslationTableModel) -> None:
        current = model.data(model.index(row, model._columns.index("translation")), Qt.DisplayRole)
        text, ok = QInputDialog.getText(self, "Edit Translation", "Translation:", text=str(current))
        if ok:
            idx = model.get_true_indexes([row])
            self.history.push(TranslationCommand(
                model=model,
                idxs=idx,
                translations=text,
                levels=TranslationLevel.VERIFIED,
                description=f"Edit: {row}"
            ))
            
            idx = model.get_true_indexes([row])
            # When manually editing, assume the user verifies the translation, so set level to VERIFIED.
            self.share_translations(idx.tolist(), need_confirmation=True, max_level=TranslationLevel.VERIFIED, is_filtered=False)
            
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            # If currently inline editing, let the view handle the enter key (usually commits the edit)
            if self.state() == QAbstractItemView.EditingState:
                super().keyPressEvent(event)
                return

            # edit the selected row using the same dialog as the context menu
            sel = self.selectionModel().selectedRows()
            if not sel:
                return
            row = sel[0].row()
            model = self.model()
            if not isinstance(model, TranslationTableModel):
                return
            self.edit_translation_row(row, model)
            return
        super().keyPressEvent(event)
        
    def translate_rows_with_api(self, rows: list[QModelIndex], only_first_unique=True):
        model = self.model()
        assert isinstance(model, TranslationTableModel)
        filtered_idxs = pd.Index((idx.row() for idx in rows))
        if only_first_unique:
            filtered_idxs = model.get_first_unique_original_idxs(filtered_idxs, is_filtered=True)        
        originals = model.filtered_df.iloc[filtered_idxs]["original"].tolist()
        idxs = model.get_true_indexes(filtered_idxs)
        translations = self.translator.batch_translate(originals)
        self.history.push(TranslationCommand(
            model=model,
            idxs=idxs, # must use true indexes, since when undo/redo, the filtered indexes may point to different rows
            translations=pd.Series(translations, index=idxs),
            levels=TranslationLevel.API,
            description=f"API: {len(rows)} rows"
        ))
        return idxs, translations
        
    def show_share_translation_confirmation(self):
        # Display the confirmation box
        if confirm:=(settings.get("confirm.shareTranslation")) is not None:
            # User chose to not show again, use the saved preference
            return confirm
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Confirm Action")
        msg_box.setText(L["confirmationMessage.shareTranslation"])
        check_box = QCheckBox(L["confirmationMessage.dontAskAgain"])
        msg_box.setCheckBox(check_box)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        # Handle user selection
        result = msg_box.exec()
        if check_box.isChecked():
            settings['confirm.shareTranslation'] = False
        if result == QMessageBox.StandardButton.Yes:
            return True
        else:
            return False
    
    def share_translations(self, indxes:list[int], need_confirmation: bool, max_level=TranslationLevel.UNTRANSLATED, is_filtered=False):
        model = self.model()
        assert isinstance(model, TranslationTableModel)
        if not model.is_same_original_exists(indxes, is_filtered):
            return
        if need_confirmation and not self.show_share_translation_confirmation():
            return
        for idx in indxes:
            share_command = ShareTranslationCommand(
                model, idx, description=f"Share Translation for idx {idx}",
                max_level=max_level # Only share to text units that are currently untranslated, to avoid overwriting existing translations at higher levels. This can be adjusted based on user preference.
            )
            self.history.push(share_command)

    def show_context_menu(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        model = self.model()
        if not isinstance(model, TranslationTableModel):
            return
        menu = QMenu(self)
        
        api_action =   menu.addAction(L['rightClick.translateWithAPI'])
        edit_action =  menu.addAction(L['rightClick.editTranslation'])
        reset_action = menu.addAction(L['rightClick.resetTranslation'])
        copy_action =  menu.addAction(L['rightClick.copyOriginal'])

        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action == api_action:
            rows = self.selectionModel().selectedRows()
            true_idxs, _ = self.translate_rows_with_api(rows)
            self.share_translations(true_idxs.tolist(), need_confirmation=False, max_level=TranslationLevel.UNTRANSLATED, is_filtered=False)

        elif action == edit_action:
            self.edit_translation_row(row, model) # share translation is handled in the edit_translation_row method, which will set the level to VERIFIED
            
        elif action == reset_action:
            rows = self.selectionModel().selectedRows()
            idxs = model.get_true_indexes([idx.row() for idx in rows])
            self.history.push(TranslationCommand(
                model=model,
                idxs=idxs,
                translations=model.df.iloc[idxs]["original"],
                levels=TranslationLevel.UNTRANSLATED,
                description=f"Reset: {row}"
            ))
        elif action == copy_action:
            original = model.data(model.index(row, model._columns.index("original")), Qt.DisplayRole)
            QApplication.clipboard().setText(str(original))

class TranslationTabWidget(QTabWidget):
    tab_exist_signal = pyqtSignal(bool)  # file_name
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs: IndexedOrderedDict[str, TranslationTableView] = IndexedOrderedDict()  # file_name -> TranslationTableView
        self.dictionaries: IndexedOrderedDict[str, TranslationDictionary] = IndexedOrderedDict()  # file_name -> TranslationDictionary
    # ---------- Overrides ----------
    def addTab(self, widget: TranslationTableView, title: str): 
        # Type hinting for the widget parameter to ensure it's a TranslationTableView, which allows us to access its model and other specific methods if needed in the future.
        assert isinstance(widget, TranslationTableView), "Only TranslationTableView instances can be added to TranslationTabWidget"
        super().addTab(widget, title)
        self.tab_exist_signal.emit(True)
    
    def removeTab(self, index: int):
        if index < 0 or index >= self.count():
            return
        key = self.tabs.keys()[index]
        self.tabs.pop(key)  # Remove from the tabs dict based on index
        super().removeTab(index)
        logger.debug("Tab removed: %s, %d remaining", key, len(self.tabs))
        if not self.tabs:            
            self.tab_exist_signal.emit(False)
        
    def currentWidget(self) -> Optional[TranslationTableView]:
        widget = super().currentWidget()
        if not isinstance(widget, TranslationTableView):
            logger.warning("Current widget is not a TranslationTableView: %s", type(widget))
            return None
        return widget
    
    def currentModel(self) -> Optional[TranslationTableModel]:
        if not (current_widget := self.currentWidget()):
            return None
        model = current_widget.model()
        if not isinstance(model, TranslationTableModel):
            return None
        return model
    # ---------- END of Overrides ----------
    def add_translation_tab(self, file_name: str, model: Optional[TranslationTableModel] = None) -> TranslationTableView:
        if file_name in self.tabs:
            return self.tabs[file_name]
        new_tab = TranslationTableView(self)
        model = model or TranslationTableModel([])
        new_tab.setModel(model)
        self.tabs[file_name] = new_tab
        self.addTab(new_tab, Path(file_name).name)
        return new_tab
    
    def focus_tab(self, file_name: str):
        if file_name not in self.tabs:
            return
        index = self.indexOf(self.tabs[file_name])
        if index != -1:
            self.setCurrentIndex(index)
    
    def chs2cht_current_tab(self):
        current_model = self.currentModel()
        if current_model is not None:
            current_model.chs2cht()
    
    def cht2chs_current_tab(self):
        current_model = self.currentModel()
        if current_model is not None:
            current_model.cht2chs()
    
    def save_current_tab(self):
        """
        If dictionary for the current tab already exists, update and save it;
        otherwise, create a new dictionary from the current tab's model and save it.
        """
        if (model := self.currentModel()) is None:
            return
        file_path = self.tabText(self.currentIndex())
        dictionary = self.dictionaries.get(file_path)
        if dictionary is None:
            dictionary = TranslationDictionary(
                df=model.df,
                source_lang=settings.SOURCE_LANG,
                target_lang=settings.TARGET_LANG
            )
        save_dir = Path(settings.user_dict_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        dictionary.save(save_dir/file_path)
        
    def load_dictionary_to_current_tab(self, dict_path: str|Path, keys: Optional[list[str]] = None):
        """load translations from the specified dictionary to the current tab."""
        current_tab = self.currentWidget()
        if current_tab is None:
            return
        current_model = current_tab.model()
        if not isinstance(current_model, TranslationTableModel):
            return
        self.apply_dictionary(dict_path, target_tab=self.tabText(self.currentIndex()), keys=keys)

    def load_dictionary(self, file_path: str|Path)-> TranslationDictionary:
        file_path = Path(file_path).absolute()
        dictionary = TranslationDictionary.load(file_path.with_suffix('.csv'))
        self.dictionaries[file_path.as_posix()] = dictionary
        return dictionary
    
    def apply_dictionary(self, dict_path: str|Path, target_tab:str|Path|None = None, keys: Optional[list[str]] = None):
        """Apply translations from the specified dictionary to the target tab.
        
        Arguments:
            dict_path (str|Path): The path to the dictionary CSV file.
            target_tab (Optional[str|Path]): The file name of the target tab to apply translations to. If None, it will apply to the currently active tab. Default is None.
            keys (Optional[list[str]]): 
                The columns to use as keys for matching translations. \\
                If None, it will use `["json_path", "original"]`.
        """
        dict_path = Path(dict_path).absolute().as_posix()
        if target_tab is None:
            target_tab = dict_path
        else:
            target_tab = Path(target_tab).absolute().as_posix()
            
        if (tab := self.tabs.get(target_tab)) is None:
            return
            
        model = tab.model()
        assert isinstance(model, TranslationTableModel), "Tab's model is not a TranslationTableModel"
        
        dictionary = self.dictionaries.get(dict_path) or self.load_dictionary(dict_path)
        
        # Apply the dictionary using the model's new method
        model.apply_dictionary(dictionary, keys=keys)
        
class TranslationCommand(QUndoCommand):
    """A command to apply a batch of changes to the DataFrame for undo/redo."""
    def __init__(
        self, model: TranslationTableModel, 
        idxs: pd.Index, 
        translations: pd.Series|str,
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