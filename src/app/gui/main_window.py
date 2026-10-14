import json
import logging
from pathlib import Path
from typing import Optional, override, Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QCloseEvent, QAction, QShortcut, QUndoStack
from PySide6.QtWidgets import (
    QLabel, QCheckBox, QFileDialog, QMainWindow, QWidget, 
    QVBoxLayout, QSplitter, 
    QMessageBox, QDialog, 
)
from qt_extensions.core import TypedSignal

from app.gui.dialogs.settings import SettingsDialog
from app.gui.dialogs.translation import TranslationDialog
from app.gui.theme import ThemeManager
from app.translation_table import TranslationTabWidget
from app.language import LanguagePack
from app.settings import Settings
import plugins
from ..translation_table import EditType 
from .menu_utils import initialize_menu
from .dialogs.search import SearchDialog
from .dialogs.dictionary_import import ImportDictionaryDialog
from .components import TopBar, BottomPanel, RecentFilesMenu, ConsoleWidget
logger = logging.getLogger(__name__)
L = LanguagePack()


class TranslationApp(QMainWindow):
    edit_current_file_requested = TypedSignal(EditType)
    save_current_file_requested = TypedSignal(str)
    save_translation_requested = TypedSignal()
    load_dir_requested = TypedSignal(str)
    load_file_requested = TypedSignal(str)
    load_workspace_requested = TypedSignal(str)
    import_from_file_requested = TypedSignal(str)
    import_from_dict_requested = TypedSignal(Path, list[str])
    batch_operation_requested = TypedSignal(Path)  # Signal to request batch operations with a list of operation dicts
    
    def __init__(self, settings: Settings):
        super().__init__()
        self._current_undo_stack = None
        self.settings = settings
        L.set_language(self.settings.language)
        ThemeManager().set_theme(dark = settings.dark_mode, FONT_SIZE = f"{settings.font_size}pt") # Apply theme based on settings at startup
        # 1. Inintialize UI
        self.setWindowTitle("RPG Translator")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)
        
        # Initialize the undo/redo actions first to be added and linked
        self.undo_action = QAction("Undo", self) 
        self.redo_action = QAction("Redo", self)
        self.undo_action.triggered.connect(lambda: self._current_undo_stack and self._current_undo_stack.undo())
        self.redo_action.triggered.connect(lambda: self._current_undo_stack and self._current_undo_stack.redo())
        
        self.init_ui()
        self.init_hotkeys()
        # 2. Register callbacks
        self.settings.setting_changed.connect(self.lru_menu.refresh)  # Refresh recent files menu when settings change
        
    @override
    def closeEvent(self, a0: QCloseEvent):
        # save the current state of the application
        open_tabs = list(self.translation_table.tabs.keys())
        self.settings.last_open_tabs = open_tabs
        self.settings.last_open_workspace = self.settings.workspace_dir
        self.settings.save()
        super().closeEvent(a0)

    def open_filter_menu(self):
        # Popup a filter Menu with Column: entries for columns in the table.
        if (model := self.translation_table.currentModel()) is None:
            logger.warning("No active translation tab to apply filters to.")
            return
        dialog = SearchDialog(model.filters, self)
        dialog.replace_requested.connect(model.search_and_replace)  # Connect the replace signal to the model's replace method
        # Hide the replace button (hidden when only filtering)
        dialog.replace_widget.setVisible(False)  
        dialog.exec()
        
    def init_ui(self):
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 1. Top Bar
        self.top_bar = TopBar(self.settings)
        self.top_bar.filter_clicked.connect(self.open_filter_menu)
        self.top_bar.workspace_clicked.connect(self.open_load_workspace_dialog)
        
        # 2. Translation Table
        self.translation_table = TranslationTabWidget()
        self.translation_table.setTabsClosable(True)
        # self.translation_table.tabCloseRequested.connect(self.translation_table.removeTab)

        self.init_menu_bar()
        
        # 4. Bottom Panel
        self.bottom_panel = BottomPanel(L, self.settings, self)
        
        # 5. Bottom Bar (show the current file full path)
        self.bottom_bar = QLabel()
        self.bottom_bar.setFixedHeight(20)
        self.bottom_bar.setObjectName("ButtonBar")  # Set the object name for styling
        self.bottom_bar.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        # --- Add Widgets to the main layout --- 
        # 1. Top Bar                                      # 1. Top Bar
        self.main_layout.addWidget(self.top_bar)          
        # 2. Main Content Area (Splitter)                 # 2. Main Content Area (Splitter)
        splitter = QSplitter(Qt.Orientation.Vertical)     
        splitter.addWidget(self.translation_table)        ## 2.1 Translation Table
        splitter.addWidget(self.bottom_panel)             ## 2.2 Bottom Panel
        self.main_layout.addWidget(splitter, 1)
        # 3. Bottom Bar                                   # 3. Bottom Bar
        self.main_layout.addStretch()  # Add stretch to push the bottom bar to the bottom
        self.main_layout.addWidget(self.bottom_bar)
        
        # Register shortcuts to show/hide the bottom panel (ctrl+`)
        self.toggle_console_shortcut = QShortcut(QKeySequence("Ctrl+`"), self)
        self.toggle_console_shortcut.activated.connect(self.toggle_console)
    
        self.toggle_bottom_panel_shortcut = QShortcut(QKeySequence("Ctrl+j"), self)
        self.toggle_bottom_panel_shortcut.activated.connect(self.toggle_bottom_panel)
    
    def toggle_bottom_panel(self):
        """Toggle the visibility of the bottom panel."""
        is_visible = not self.bottom_panel.isVisible()
        self.bottom_panel.setVisible(is_visible)
        return is_visible
    
    def toggle_console(self):
        """Switch the focus to the console input or close the bottom panel"""
        if self.focusWidget() == self.bottom_panel.console_tab.line_edit:
            # If the console input is focused, toggle the bottom panel visibility
            self.toggle_bottom_panel()
        else:
            # If the console input is not focused, show the bottom panel and focus the console input
            self.bottom_panel.setVisible(True)
            self.bottom_panel.setCurrentWidget(self.bottom_panel.console_tab)
            self.bottom_panel.console_tab.line_edit.setFocus()

    def init_menu_bar(self):
        self.lru_menu = RecentFilesMenu(L["menu.file.recent_files"], self.settings.recent_files)
        menu_def = {
            "file.load_game_file": self.request_load_file,
            "file.load_workspace": self.open_load_workspace_dialog,
            "file.open_directory": self.request_load_dir,
            "file.import.from_file": self.request_import_from_file,
            "file.import.from_dict": self.request_import_from_dict,
            # "file.new_workspace": self.open_load_workspace_dialog,
            "file.save_translation": self.save_translation_requested.emit,
            "file.recent_files": self.lru_menu,
            "file.save_game_file": lambda :self.save_current_file_requested.emit("{default}"),
            "file.save_game_file_as": lambda :self.save_current_file_requested.emit("{custom}"),
            "settings": self.open_settings,
            "edit.undo": self.undo_action,
            "edit.redo": self.redo_action,
            # Consider moving chinese conversion to batch operations as well
            "tools.chinese_conversion.chs2cht": lambda: self.edit_current_file_requested.emit(EditType.CHS2CHT),
            "tools.chinese_conversion.cht2chs": lambda: self.edit_current_file_requested.emit(EditType.CHT2CHS),
            "tools.batch_operation.load_yaml": lambda: self.request_batch_operation("yaml"),
            "tools.batch_operation.load_json": lambda: self.request_batch_operation("json"),
            "tools.share_top_translations": lambda: self.edit_current_file_requested.emit(EditType.SHARE_TOP_LV),
        } 
        self.menus = initialize_menu(menu_def, self.menuBar(), root_menu_name="menu", tr=L.__getitem__)
        self.lru_menu.recent_file_selected.connect(self.load_file_requested.emit)  # Connect recent file selection to load file signal
        self.settings.workspace_changed.connect(self.update_file_menu)
        self.translation_table.tab_exist_signal.connect(self.on_tab_exist_changed)
        self.on_tab_exist_changed(False)  # Initially disable save actions since no tab is open

    @property
    def console(self) -> ConsoleWidget:
        return self.bottom_panel.console_tab
    
    def on_tab_exist_changed(self, exist: bool):
        """Enable or disable the save translation action based on whether a tab with a loaded file exists."""
        self.menus["file.save_translation"].setEnabled(exist)
        self.menus["file.save_game_file"].setEnabled(exist)
        self.menus["file.save_game_file_as"].setEnabled(exist)
        
    def update_file_menu(self, _:Optional[str] = None):
        extractor = plugins.extractors[self.settings.plugin]
        if "file.open_directory" in self.menus:
            self.menus["file.open_directory"].setEnabled(bool(extractor.SUPPORTED_DIR_TYPE))
        else:
            logger.error("Could not find 'file.open_directory' menu to update its enabled state.")
        
    def update_bottom_bar(self, file_path: Optional[str]):
        """Update the bottom bar to show the current file path."""
        if file_path:
            self.bottom_bar.setText(file_path)
        else:
            self.bottom_bar.setText("No file loaded.")
            
    def init_hotkeys(self):
        self.hotkeys = {
            "save": QShortcut(QKeySequence.StandardKey.Save, self),
            "search": QShortcut(QKeySequence.StandardKey.Find, self),
        }
        self.hotkeys["save"].activated.connect(self.save_translation_requested.emit)
        self.hotkeys["save"].setEnabled(False)  # Disable save hotkey until a tab with a loaded file exists
        self.hotkeys["search"].activated.connect(self.open_filter_menu)
        self.translation_table.tab_exist_signal.connect(lambda exist:self.hotkeys["save"].setEnabled(exist))

        self.undo_action.setShortcuts(QKeySequence.StandardKey.Undo)   
        self.redo_action.setShortcuts(QKeySequence.StandardKey.Redo) 
        self.addAction(self.undo_action) # Ctrl+Z / Cmd+Z
        self.addAction(self.redo_action) # Ctrl+Y / Cmd+Shift+Z
    
    def bind_undo_redo_actions(self, stack: Optional[QUndoStack]):
        if self._current_undo_stack is stack:
            return
            
        if self._current_undo_stack is not None:
            try:
                # Disconnect logic signals
                self._current_undo_stack.canUndoChanged.disconnect(self.undo_action.setEnabled)
                self._current_undo_stack.canRedoChanged.disconnect(self.redo_action.setEnabled)
            except (TypeError, RuntimeError):
                # This is expected when the stack was destroyed after closing a tab
                pass
        
        self._current_undo_stack = stack
        if stack is not None:
            # Connect logic signals
            stack.canUndoChanged.connect(self.undo_action.setEnabled)
            stack.canRedoChanged.connect(self.redo_action.setEnabled)
            # Update initial state
            self.undo_action.setEnabled(stack.canUndo())
            self.redo_action.setEnabled(stack.canRedo())
        else:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
        
    def open_load_workspace_dialog(self):
        workspace_dir = QFileDialog.getExistingDirectory(self, L["file_dialog.select_workspace_dir"])
        if workspace_dir:
            self.load_workspace_requested.emit(workspace_dir)
            
    def get_file_filters(self) -> str:
        extractor = plugins.extractors[self.settings.plugin]()
        supported_types = extractor.SUPPORTED_FILES_TYPES
        file_filters = ";;".join(f"{ft.upper()} Files (*{ft})" for ft in supported_types)+f";;All Files (*.*)"
        return file_filters
    
    def request_load_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, L["file_dialog.select_directory"])
        if dir_path:
            self.load_dir_requested.emit(dir_path)  # Emit the signal to load the directory, which will be handled by the presenter
    
    def request_import_from_file(self):
        file_filters = self.get_file_filters()
        file_path, _ = QFileDialog.getOpenFileName(self, L["file_dialog.select_game_file"], "", file_filters)
        if file_path:
            self.import_from_file_requested.emit(file_path)  # Emit the signal to import from the selected file

    def request_import_from_dict(self):
        """This is a function to potientially replace:
        open_import_from_dict_dialog+presenter.handle_import_from_dict_request
        presenter.handle_import_from_dict_request will only be called if a file is selected
        """
        path, _ = QFileDialog.getOpenFileName(
            self, L["file_dialog.select_translation_dictionary"], 
            self.settings.user_dict_dir, "CSV Files (*.csv)"
        )
        if path and (file_path:= Path(path)).exists():
            # Show a dialog to select which columns to use as keys
            dialog = ImportDictionaryDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.import_from_dict_requested.emit(file_path, dialog.keys)
            else:
                logger.info("Import dictionary operation cancelled.")

    def request_load_file(self):
        file_filters = self.get_file_filters()
        file_path, _ = QFileDialog.getOpenFileName(self, L["file_dialog.select_game_file"], "", file_filters)
        if not file_path:
            return  # User cancelled the file dialog
        self.load_file_requested.emit(file_path)  # Emit the signal to load the file, which will be handled by the presenter

    def request_batch_operation(self, file_extention: Literal['yaml', 'json']):
        """Request a batch operation of the specified type ('yaml' or 'json')."""
        if file_extention == 'yaml': 
            _filter = "YAML Files (*.yaml *.yml)"
        elif file_extention == 'json':
            _filter = "JSON Files (*.json)"
        file_path,_ = QFileDialog.getOpenFileName(self, L["file_dialog.select_file"], "", _filter)
        self.batch_operation_requested.emit(Path(file_path))
    
    def open_edit_translation_dialog(self, original: str, translation: str) -> Optional[str]:
        dialog = TranslationDialog(self.settings, original, translation, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.translation
        return None

    def show_share_translation_confirmation(self)-> bool:
        # Display the confirmation box
        if confirm:=(self.settings.confirmations.share_translation) is not None:
            # User chose to not show again, use the saved preference
            return confirm
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Confirm Action")
        msg_box.setText(L["confirm_msg.share_translation"])
        check_box = QCheckBox(L["confirm_msg.dont_ask_again"])
        msg_box.setCheckBox(check_box)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        # Handle user selection
        result = (msg_box.exec()==QMessageBox.StandardButton.Yes)
        if check_box.isChecked():
            self.settings['confirmations.share_translation'] = result
        return result
    
    def show_unsaved_changes_dialog(self, file_name: str) -> str:
        # Display the confirmation box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(L["confirm_msg.unsaved_changes"])
        msg_box.setText(L["confirm_msg.unsaved_changes_desc"].format(file_name=file_name))
        msg_box.setInformativeText(L["confirm_msg.unsaved_changes_desc2"])
        msg_box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
        # Handle user selection
        result = None
        clicked_button = msg_box.exec()
        if clicked_button == QMessageBox.StandardButton.Save:
            result = "save"
        elif clicked_button == QMessageBox.StandardButton.Discard:
            result = "discard"
        elif clicked_button == QMessageBox.StandardButton.Cancel:
            result = "cancel"
        else:
            logger.warning("Unexpected button clicked in unsaved changes dialog: %s", clicked_button)
            result = "cancel"
        return result
    
    def open_save_game_file_dialog(self, default_file_path: str) -> Optional[str]:
        if Path(default_file_path).is_dir():
            save_path = QFileDialog.getExistingDirectory(
                self, L["file_dialog.save_translated_file"], default_file_path
            )
        else:
            save_path, _ = QFileDialog.getSaveFileName(
                self, L["file_dialog.save_translated_file"], default_file_path, 
                filter = self.get_file_filters()
            )
        if not save_path:
            return  # User cancelled the save dialog
        return save_path

    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec()== QDialog.DialogCode.Accepted:
            dialog.save_settings()
            L.set_language(self.settings.language)
            logger.debug("Settings saved")
            try:
                self.settings.save()
            except Exception:
                logger.exception("Failed to save settings.json")
            ThemeManager().set_theme(dark = self.settings.dark_mode, FONT_SIZE = f"{self.settings.font_size}pt")  # Apply theme based on settings
        else:
            logger.debug("Settings dialog cancelled")
