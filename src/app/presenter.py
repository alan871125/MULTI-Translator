from pathlib import Path
from itertools import cycle, islice
from typing import Literal, Optional, Sequence
import logging
from PyQt5.QtWidgets import QApplication
from app.gui.main_window import TranslationApp
from core.translation import Translator

from .models.session import TranslationSession
from .models.translation_table_model import TranslationLevel, TranslationTableProxyModel
from .translation_table import EditType, TranslationTabWidget
from .settings import WORKSPACE_FILE_EXTENSION, Settings

logger = logging.getLogger(__name__)

class TranslationAppPresenter:
    def __init__(
        self, main_window: TranslationApp, settings: Settings, session: TranslationSession, translation_tab_widget: TranslationTabWidget
    ):
        self.settings: Settings = settings
        self.session: TranslationSession = session
        self.translation_tab_widget: TranslationTabWidget = translation_tab_widget
        self.translator = Translator(settings)
        self.main_window:TranslationApp = main_window
        self.connect_signals()
        if self.settings.restore_last_session:
            self.restore_session()  # Restore session before connecting signals to ensure the UI
            
    def connect_signals(self):
        """Connects signals from the view to the appropriate handler methods in the presenter."""
        self.main_window.load_file_requested.connect(self.handle_open_file_request)
        self.main_window.load_dir_requested.connect(self.handle_open_dir_request)
        self.main_window.import_from_file_requested.connect(self.handle_import_from_file_request)
        self.main_window.import_from_dict_requested.connect(self.handle_import_from_dict_request)
        self.main_window.save_translation_requested.connect(self.handle_save_translation_request)  # Assuming saving also closes the file, adjust if not
        self.main_window.save_current_file_requested.connect(self.handle_save_current_file_request)
        self.main_window.edit_current_file_requested.connect(self.handle_edit_current_file_request)
        self.translation_tab_widget.tabCloseRequested.connect(self.handle_close_file_request)
        self.translation_tab_widget.currentChanged.connect(self.handle_tab_changed)
        self.translation_tab_widget.open_dropped_file_request.connect(self.handle_open_file_request)
        
    def restore_session(self, workspace:Optional[Path|str]=None):
        if workspace is None:
        # Load previous workspace
            self.settings.load_last_open_workspace()
        elif Path(workspace).exists():
            self.settings.update_workspace(workspace)
        # Load the previously open tabs from settings and attempt to restore them
        for file_path in self.settings.last_open_tabs:
            if Path(file_path).exists():
                if Path(file_path).is_dir():
                    self.handle_open_dir_request(file_path)  # Directly call the handler to open the directory, which will create the model and tab
                else:
                    self.handle_open_file_request(file_path)  # Directly call the handler to open the file, which will create the model and tab
            else:
                logger.warning(f"Previously open file {file_path} not found. Skipping.")
    
    def handle_tab_changed(self, index: int):
        logger.debug("tab changed signal received for tab index: %d", index)
        if index == -1:  # No tabs are open
            self.main_window.bind_undo_redo_actions(None)
            return
        file_path = self.translation_tab_widget.tabs.keys()[index]
        history = self.session.get_history_stack(file_path)
        self.main_window.bind_undo_redo_actions(history)
        self.main_window.update_bottom_bar(file_path)  # Update the bottom bar with the current file path
        
    def handle_edit_current_file_request(self, edit_type: EditType):
        """Handles a request to edit a file."""
        file_path = self.translation_tab_widget.get_current_file_path()
        if file_path is None:
            # TODO: This case should ideally never happen because the edit action should be disabled when no file is open
            logger.warning("No file is currently open to edit.")
            return
        match edit_type:
            case EditType.CHS2CHT:
                self.session.chs2cht(file_path)
            case EditType.CHT2CHS:
                self.session.cht2chs(file_path)
            case _:
                raise NotImplementedError(f"Handling for EditType {edit_type} is not implemented.")

    def handle_edit_translation_request(self, file_path:Path|str, row_idxs: Sequence[int], EditType: EditType):
        """Handles a request to edit a translation. 
        """
        key = Path(file_path).absolute().as_posix()
        if (model := self.session.models.get(key)) is None:
            logger.warning(f"Attempted to edit a translation for a file that is not open: {file_path}")
            return
        idxs = model.get_true_indexes(row_idxs)
        match EditType:
            case EditType.MANUAL:
                current_text = model.df.iloc[idxs[0]]['translation']  # Get the current translation of the first selected row to pre-fill the dialog
                translations = self.main_window.open_edit_translation_dialog(current_text)
                if translations is not None:
                    level = TranslationLevel.VERIFIED
                else:
                    return
            case EditType.API:
                current_text = model.df.loc[idxs,'translation']
                translations = self.translator.batch_translate(current_text.tolist())
                _idxs = idxs
                idxs, translations = zip(*[(i, trans) for i, trans in zip(idxs, translations) if trans is not None])
                level=TranslationLevel.API
                failed_count = len(_idxs) - len(idxs)
                if failed_count > 0:
                    logger.warning(f"API translation failed for {failed_count} out of {len(_idxs)} selected rows.")
            case EditType.RESET:
                translations = model.df.loc[idxs,'original'].astype(str)
                level = TranslationLevel.UNTRANSLATED
            case EditType.PASTE:
                clipboard_text = QApplication.clipboard().text()
                if not clipboard_text:
                    logger.warning("Clipboard is empty. Nothing to paste.")
                    return
                translations = list(islice(cycle(clipboard_text.split('\r\n')), len(idxs)))  # Repeat the clipboard text if there are more selected rows than lines in the clipboard
                level = TranslationLevel.VERIFIED
            case _:
                raise ValueError(f"Unknown EditType: {EditType}")
        share = self.main_window.show_share_translation_confirmation()
        self.session.set_translations(file_path, idxs, translations=translations, level=level,share=share)
    
    def handle_copy_cells_request(self, file_path: str|Path, row_idxs: list[int], col_idx: int):
        """Handles a request to copy the contents of one or more cells to the clipboard.
        Triggered by the user selecting "Copy" from the context menu after right-clicking on a cell or selection of cells in the translation table, or by using the standard copy keyboard shortcut (e.g., Ctrl+C).
        """
        key = Path(file_path).absolute().as_posix()
        if (model := self.session.models.get(key)) is None:
            logger.warning(f"Attempted to copy cells for a file that is not open: {file_path}")
            return
        # Get the text of the selected cells and join them with newlines for copying to clipboard
        idxs = model.get_true_indexes(row_idxs)
        cell_texts = model.df.iloc[idxs, col_idx].astype(str).tolist()
        clipboard_text = "\r\n".join(cell_texts)
        QApplication.clipboard().setText(clipboard_text)
    
    def handle_save_current_file_request(self, save_path: str|Path|None):
        """Handles a request to save the current file.
        
        Triggered by Save File action in MenuBar
        Or by using a keyboard shortcut for saving (e.g., Ctrl+S)
        """
        # get current file path to locate model(for self.session) and to generate default save path if needed
        if (current_file_path :=self.translation_tab_widget.get_current_file_path()) is None:
            logger.warning("Current translation tab has no associated file path to generate default save path.")
            return
        current_file_path = Path(current_file_path)
        key = Path(current_file_path).absolute().as_posix()
        #TODO: create a request container class for better type hinting
        if "{custom}" == str(save_path):
            if not (custom_path := self.main_window.open_save_game_file_dialog(key)):
                return # User cancelled the save dialog
            save_path = custom_path
        elif "{default}" == str(save_path):             # Generate default save path based on the current file path
            save_path = None  # Let the model's save_to_file method handle generating the default path based on the original file path
        
        self.session.save_file(key, save_path)
    
    def handle_save_translation_request(self):
        """Handles a request to save the current translations to a file.
        
        Triggered by Save File action in MenuBar
        Or by using a keyboard shortcut for saving (e.g., Ctrl+S)
        """
        
        if (current_file_path :=self.translation_tab_widget.get_current_file_path()) is None:
            logger.warning("Current translation tab has no associated file path to generate default save path.")
            return
        key = Path(current_file_path).absolute().as_posix()
        self.session.save_dictionary(key)
        
    def handle_set_level_request(self, file_path:Path|str, row_idxs: Sequence[int], level: TranslationLevel):
        """Handles a request to set the translation level for one or more translations.
        This is typically called when the user:
            - right-clicks a cell or selection of cells in the translation table and selects "Set Level" from the context menu.
            - uses a batch operation to set the level of multiple translations at once.
        """
        self.session.set_level(file_path, row_idxs, level)

    def create_translation_tab(self, path: str|Path):
        path = Path(path).absolute()
        # Create tab in the TranslationTabWidget
        tab = self.translation_tab_widget.add_translation_tab(path.as_posix())
        tab.edit_translation_requested.connect(
            lambda idxs,edit_type: self.handle_edit_translation_request(path, idxs, edit_type)
        )
        tab.set_level_requested.connect(
            lambda idxs, level: self.handle_set_level_request(path, idxs, level)
        )
        tab.copy_cells_requested.connect(
            lambda idxs, col: self.handle_copy_cells_request(path, idxs, col)
        )
        return tab
    
    def handle_open_workspace_request(self, workspace_path: str|Path):
        """Handles a request to open a workspace file.
        
        Triggered by Open Workspace action in MenuBar
        Or by drag-and-dropping a workspace file into the application window (unimplemented)
        """
        workspace_path = Path(workspace_path).absolute()
        assert workspace_path.exists() and workspace_path.suffix == WORKSPACE_FILE_EXTENSION, f"Provided path is not a valid workspace file: {workspace_path}"
        self.restore_session(workspace_path)
        
    def handle_open_file_request(self, file_path: str|Path):
        """Handles a request to open a file.
        
        Triggers by Open File action in MenuBar
        Or by drag-and-dropping a file into the application window (unimplemented)
        """
        file_path = Path(file_path).absolute()
        if file_path.suffix == WORKSPACE_FILE_EXTENSION:
            # If it's workspace file, treat it as a workspace
            return self.restore_session(file_path)
        elif file_path.is_dir():
            return self.handle_open_dir_request(file_path)  # Directly call the handler to open the directory, which will create the model and tab
        # Create model for the file in the session
        if (model := self.session.open_file(file_path)) is None:
            return
        # Load existing user dictionary
        dict_path = Path(self.settings.user_dict_dir) / (Path(file_path).with_suffix('.csv').name)
        if dict_path.exists():
            self.session.apply_dictionary(dict_path, file_path)
        tab = self.create_translation_tab(file_path)
        proxy_model = TranslationTableProxyModel()
        proxy_model.setSourceModel(model)
        tab.setModel(proxy_model)
        if model.undo_stack is not None:
            model.undo_stack.cleanChanged.connect(
                lambda: self.translation_tab_widget.update_tab_save_status(file_path.as_posix())
            )
            self.translation_tab_widget.update_tab_save_status(file_path.as_posix())
        
    def handle_close_file_request(self, index:int):
        """Handles a request to close a file.
        
        Triggered by Close File action in MenuBar
        Or by clicking the close button on a tab in the TranslationTabWidget
        """
        # check for unsaved changes and prompt user to save if needed before closing
        tab_text = self.translation_tab_widget.tabText(index)
        if tab_text.endswith("*"):  # Unsaved changes indicated by a "*" at the end
            response = self.main_window.show_unsaved_changes_dialog(tab_text[:-1])
            if response == "cancel":
                return  # User cancelled the close action
            elif response == "save":
                self.handle_save_current_file_request(None)  # Save current file before closing, passing None to use default save path
        # When response == 'discard'
        logger.debug("Close file request received for tab index: %d", index)
        self.session.close_index(index)
        self.translation_tab_widget.removeTab(index)

    def handle_open_dir_request(self, dir_path: str|Path):
        """Handles a request to open a directory.
        
        Triggered by Open Directory action in MenuBar
        Or by drag-and-dropping a directory into the application window (unimplemented)
        """
        dir_path = Path(dir_path).absolute()
        assert dir_path.is_dir() and dir_path.exists(), f"Provided path is not a valid directory: {dir_path}"
        if (model := self.session.open_dir(dir_path)) is None:
            return
        # Load existing user dictionary
        dict_path = Path(self.settings.user_dict_dir) / (Path(dir_path).with_suffix('.csv').name)
        if dict_path.exists():
            self.session.apply_dictionary(dict_path, dir_path)
        # Create tab in the TranslationTabWidget
        tab = self.create_translation_tab(dir_path)
        proxy_model = TranslationTableProxyModel()
        proxy_model.setSourceModel(model)
        tab.setModel(proxy_model)
        if model.undo_stack is not None:
            model.undo_stack.cleanChanged.connect(
                lambda: self.translation_tab_widget.update_tab_save_status(dir_path.as_posix())
            )
            self.translation_tab_widget.update_tab_save_status(dir_path.as_posix())
    
    def handle_import_from_file_request(self, file_path: str|Path):
        """Opens a file, reads its contents, and imports the translations into the current translation table."""
        raise NotImplementedError("Import from file functionality is not yet implemented.")
    
    def handle_import_from_dict_request(self, dict_path: str|Path):
        """Opens a dictionary file, reads its contents, and imports the translations into the current translation table."""
        dict_path = Path(dict_path).absolute()
        if (current_file_path := self.translation_tab_widget.get_current_file_path()) is None:
            logger.warning("Current translation tab has no associated file path to import translations into.")
            return
        file_path = Path(current_file_path).absolute()
        if dict_path.exists():
            #TODO: Popup a dialog to confirm and select applying options (e.g. apply level)
            
            self.session.apply_dictionary(dict_path, file_path)
        else:
            logger.error(f"Dictionary file {dict_path} does not exist. Cannot import translations.")