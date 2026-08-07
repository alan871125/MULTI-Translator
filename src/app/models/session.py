
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Iterable, Optional, Sequence

from PyQt5.QtWidgets import QUndoStack
from PyQt5.QtCore import QObject, pyqtSignal

from iod import IndexedOrderedDict

from app.models.filters import TableFilters
from app.settings import Settings
from app.translation_table import logger
from core import engines
from core.translation import TranslationLevel
from core.translation.dictionary import TranslationDictionary
from core.translation.dictionary_database import TranslationDictionaryDatabase
from .translation_table_model import TranslationTableModel, TranslationCommand, ShareTranslationCommand

logger = logging.getLogger(__name__)


class TranslationSession(QObject):
    file_opened = pyqtSignal(str, TranslationTableModel)  # Signal emitted when a file is opened, with the file path and model as arguments
    file_closed = pyqtSignal(str)  # Signal emitted when a file is closed, with the file path as an argument
    
    def __init__(self, settings:Settings, filters: TableFilters, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.db = TranslationDictionaryDatabase(settings.db_path)
        self.dictionaries: dict[str, TranslationDictionary] = {}
        # Use IOD to keep aligned indexes between the models/views and the undo stacks.
        self.models: IndexedOrderedDict[str, TranslationTableModel] = IndexedOrderedDict()
        self.history_stacks: IndexedOrderedDict[str, QUndoStack] = IndexedOrderedDict()
        self.settings = settings
        self.filters = filters

    def load_dictionary(self, file_path: str|Path, name: Optional[str] = None)-> TranslationDictionary:
        file_path = Path(file_path).absolute()
        name = name or file_path.as_posix()
        dictionary = TranslationDictionary.load(file_path.with_suffix('.csv'))
        self.dictionaries[name] = dictionary
        self.db.insert_from_dataframe(dictionary.df)
        return dictionary
    
    def unload_dictionary(self, name: str):
        if name in self.dictionaries:
            del self.dictionaries[name]
            # TODO: Remove from database if needed
    
    def save_dictionary(self, key: str, save_path: Optional[str|Path] = None):
        if (model := self.models.get(key)) is None:
            raise KeyError(f"No open model found for name: {key}")
        if (dictionary := self.dictionaries.get(key)) is None:
            # Create a new dictionary if it doesn't exist
            dictionary = TranslationDictionary(
                df = model.df.copy(),
                source_lang=self.settings.SOURCE_LANG,
                target_lang=self.settings.TARGET_LANG
            )
        if save_path is None:
            name = Path(key).stem
            save_dir = Path(self.settings.user_dict_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = (save_dir/name).with_suffix('.csv')
        dictionary.save(save_path)
        history = self.get_history_stack(key)
        history.setClean()
    
    def save_file(self, file_path: str|Path, save_path: Optional[str|Path] = None):
        """Export the translated file with the engine."""
        file_path = Path(file_path).absolute()
        key = file_path.as_posix()
        if (model := self.models.get(key)) is None:
            logger.warning(f"Attempted to save a file that is not open: {file_path}")
            return
        model.save_to_file(save_path)
    
    def open_file(self, file_path: str|Path) -> Optional[TranslationTableModel]:
        file_path = Path(file_path).absolute()
        try:
            extractor = engines.extractors[self.settings.engine]()
            key = file_path.as_posix()
            stack = self.history_stacks.setdefault(key, QUndoStack())  # Create an undo stack for this file if it doesn't exist
            model = TranslationTableModel(
                data=extractor.extract_file(file_path), 
                filters=self.filters,
                file_path=file_path,
                engine=extractor,
                undo_stack=stack
            )
            self.models[key] = model
            self.file_opened.emit(key, model)
            return model
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON in file {file_path}: {e}")
            # should notify the user about the error
        except Exception as e:
            logger.error(f"Failed to open file {file_path}: {e}")
            
    def open_dir(self, dir_path: str|Path) -> Optional[TranslationTableModel]:
        dir_path = Path(dir_path).absolute()
        extractor = engines.extractors[self.settings.engine]()
        if not extractor.SUPPORTED_DIR_TYPE:
            logger.error(f"The current engine '{self.settings.engine}' does not support directory extraction.")
            return None
        elif not extractor.SUPPORTED_DIR_TYPE.is_valid(dir_path):
            logger.error(f"The directory {dir_path} is not a valid {extractor.SUPPORTED_DIR_TYPE}.")
            return None
        try:
            key = dir_path.as_posix()
            model = TranslationTableModel(
                data=extractor.extract_dir(dir_path, source_lang=self.settings.SOURCE_LANG, target_lang=self.settings.TARGET_LANG), 
                filters=self.filters,
                file_path=dir_path,
                engine=extractor,
                undo_stack=self.history_stacks.setdefault(key, QUndoStack()) 
            )
            self.models[key] = model
            self.file_opened.emit(key, model)
            return model
        except Exception as e:
            logger.error(f"Failed to open directory {dir_path}: {e}")
        
    def close_index(self, index: int):
        if index < 0 or index >= len(self.models):
            logger.warning(f"Attempted to close a file that is not open: {index}")
            return
        key = self.models.keys()[index]
        del self.models[key]
        del self.history_stacks[key]
        self.file_closed.emit(key)
        
    def close_file(self, file_path: str|Path):
        file_path = Path(file_path).absolute()
        key = file_path.as_posix()
        if key in self.models:
            del self.models[key]
            del self.history_stacks[key]
            self.file_closed.emit(key)
        else:
            logger.warning(f"Attempted to close a file that is not open: {file_path}")
            
    def get_history_stack(self, file_path: str|Path) -> QUndoStack:
        file_path = Path(file_path).absolute()
        key = file_path.as_posix()
        return self.history_stacks.setdefault(key, QUndoStack())  # Create an undo stack for this file if it doesn't exist
    
    def set_level(self, file_path: str|Path, sel: Iterable[int], level: TranslationLevel):
        """Set the translation level for the currently selected rows. This can be used in conjunction with batch operations to set the level of multiple translations at once."""
        file_path = Path(file_path).absolute().as_posix()
        if (model := self.models.get(file_path)) is None:
            logger.warning(f"Attempted to set level for a file that is not open: {file_path}")
            return
        history = self.get_history_stack(file_path)
        idxs = model.get_true_indexes(sel)
        history.push(TranslationCommand(
            model=model,
            idxs=idxs,
            translations=model.df.loc[idxs, "translation"],
            levels=level,
            description=f"Set Level: {level.name} for {len(idxs)} rows"
        ))
    
    def push_translation_command(self, file_path: str|Path, idxs: Sequence[int]|pd.Index, translations: pd.Series|str, levels: Optional[TranslationLevel] = None, description: str = "Batch Translation Edit"):
        file_path = Path(file_path).absolute().as_posix()
        if (model := self.models.get(file_path)) is None:
            logger.warning(f"Attempted to push a translation command for a file that is not open: {file_path}")
            return
        history = self.get_history_stack(file_path)
        idxs = model.get_true_indexes(idxs)
        history.push(TranslationCommand(
            model=model,
            idxs=idxs,
            translations=translations,
            levels=levels,
            description=description
        ))
        
    def set_translations(self, file_path: str|Path, idxs: Sequence[int]|pd.Index, translations: Iterable[str]|str, level: TranslationLevel = TranslationLevel.VERIFIED, share:bool = False):
        """Set the translation for the currently selected rows. This can be used in conjunction with batch operations to set the translation of multiple rows at once."""
        file_path = Path(file_path).absolute().as_posix()
        if (model := self.models.get(file_path)) is None:
            logger.warning(f"Attempted to set translation for a file that is not open: {file_path}")
            return
        history = self.get_history_stack(file_path)
        
        idxs = pd.Index(idxs) if isinstance(idxs, Iterable) else pd.Index([idxs])
        history.beginMacro(f"Set Translation for {len(idxs)} rows")
        history.push(TranslationCommand(
            model=model,
            idxs=idxs,
            translations=translations,
            levels=level,
            description=f"Set Translation for {len(idxs)} rows"
        ))
        if share:
            for idx in idxs:
                history.push(ShareTranslationCommand(
                    model, idx, description=f"Share Translation for index: {idx}"
                ))
        history.endMacro()
        
    def share_translations(self, file_path: str|Path, idxs: Sequence[int]|pd.Index, max_level: TranslationLevel = TranslationLevel.API, is_filtered: bool = True):
        """Share the translation of the specified rows to all other rows with the same original text
        
        Arguments:
            file_path (str|Path): The path to the file containing the rows to share.
            idxs (list[int]): List of row indexes to share translations from.
            max_level (TranslationLevel): The maximum translation level to consider when sharing. Only rows with a translation level less than or equal to this will be updated.
            is_filtered (bool): Whether the provided indexes are based on the currently filtered view. If True, the method will convert these to the corresponding indexes in the full DataFrame.
        """
        file_path = Path(file_path).absolute().as_posix()
        if (model := self.models.get(file_path)) is None:
            logger.warning(f"Attempted to share translations for a file that is not open: {file_path}")
            return
        history = self.get_history_stack(file_path)
        history.beginMacro(f"Share Translations for {len(idxs)} rows")
        description = "Share Translation for index: {idx}"
        for idx in idxs:
            history.push(ShareTranslationCommand(
                model, idx, description.format(idx=idx), max_level)
            )
        history.endMacro()
    
    def reset_translations(self, file_path: str|Path, idxs: list[int]|pd.Index):
        """Reset the translations of the specified rows back to their original text."""
        file_path = Path(file_path).absolute().as_posix()
        if (model := self.models.get(file_path)) is None:
            logger.warning(f"Attempted to reset translations for a file that is not open: {file_path}")
            return
        idxs=model.get_true_indexes(idxs)
        history = self.get_history_stack(file_path)
        history.push(TranslationCommand(
            model=model, idxs=idxs,
            translations=model.df.loc[idxs, "original"],
            levels=TranslationLevel.UNTRANSLATED,
            description=f"Reset Translations for {len(idxs)} rows"
        ))

    def cht2chs(self, file_path: str|Path):
        # TODO: Add to history for undo/redo
        model = self.models.get(Path(file_path).absolute().as_posix())
        if model is None:
            logger.warning(f"Attempted to convert CHT to CHS for a file that is not open: {file_path}")
            return
        model.cht2chs()
        
    def chs2cht(self, file_path: str|Path):
        # TODO: Add to history for undo/redo
        model = self.models.get(Path(file_path).absolute().as_posix())
        if model is None:
            logger.warning(f"Attempted to convert CHS to CHT for a file that is not open: {file_path}")
            return
        model.chs2cht()
    
    def apply_dictionary(self, dict_path: str|Path, target:str|Path, keys: Optional[list[str]] = None):
        """Apply translation from the specified dictionary to the target tab.
        
        Arguments:
            dict_path (str|Path): The path to the dictionary (*.csv) file.
            target (str|Path): Path to the target file. Act as a key to find the corresponding model in self.models.
            keys (Optional[list[str]]): 
                List of keys representing the identifiers of the text units.\\
                If None, `["key"]` will be used as the default.
        
        Returns:
            None
        """
        dictionary = self.load_dictionary(dict_path)
        if not (model := self.models.get(Path(target).absolute().as_posix())):
            logger.warning(f"Attempted to apply a dictionary to a file that is not open: {target}")
            return
        model.apply_dictionary(dictionary, keys=keys)

