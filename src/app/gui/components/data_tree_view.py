import sys
import shutil
from pathlib import Path
from typing import Any, Sequence, override
from venv import logger
from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PySide6.QtWidgets import QApplication, QTreeView, QFileSystemModel, QVBoxLayout, QWidget, QMenu, QInputDialog, QMessageBox
from qt_extensions.core import TypedSignal

class CheckableFileSystemModel(QFileSystemModel):
    check_state_changed = TypedSignal(str, Qt.CheckState)  # Signal to emit when a checkbox state changes
    def __init__(self, parent:QWidget|None=None):
        super().__init__(parent)
        # Dictionary to keep track of check states for paths: path -> Qt.CheckState
        self.check_states = {}

    @override
    def flags(self, index: QModelIndex|QPersistentModelIndex):
        # Add ItemIsUserCheckable to the default flags of each file/folder
        default_flags = super().flags(index)
        if index.column() == 0:  # Only show checkboxes on the first column (Name)
            return default_flags | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable
        return default_flags
    
    @override
    def data(self, index: QModelIndex|QPersistentModelIndex, /, role: int = Qt.ItemDataRole.DisplayRole):
        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            file_path = self.filePath(index)
            # Default to Unchecked if not set
            return self.check_states.get(file_path, Qt.CheckState.Unchecked)
        
        return super().data(index, role)

    @override
    def setData(self, index: QModelIndex|QPersistentModelIndex, value: Any, /, role:int=Qt.ItemDataRole.EditRole):
        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            file_path = self.filePath(index)
            self.check_states[file_path] = Qt.CheckState(value)
            self.check_state_changed.emit(file_path, Qt.CheckState(value))
            # Emit dataChanged so the view updates the checkbox visually
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
            
        return super().setData(index, value, role)
    from functools import singledispatchmethod
    @singledispatchmethod
    def set_check_state(self, file_path: str, state: Qt.CheckState|bool):
        """Set the check state for a given file path."""
        if isinstance(state, bool):
            state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        index = self.index(file_path)
        if index.isValid():
            self.check_states[file_path] = state
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])

    @set_check_state.register # set with index
    def _(self, index: QModelIndex|QPersistentModelIndex, state: Qt.CheckState|bool):
        """Set the check state for a given index."""
        if isinstance(state, bool):
            state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        file_path = self.filePath(index)
        self.check_states[file_path] = state
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])


class CheckableFileExplorer(QWidget):
    def __init__(self, root_path:str|None=None, name_filters:Sequence[str]|None=None, parent:QWidget|None=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Setup Model
        self.model = CheckableFileSystemModel(self)
        if not root_path:
            root_path = str(Path.cwd())
        elif not Path(root_path).exists():
            logger.warning(f"Root path '{root_path}' does not exist. Falling back to cwd.")
            root_path = str(Path.cwd())
            
        self.model.setRootPath(root_path)
        
        if name_filters:
            self.model.setNameFilters(name_filters)
            self.model.setNameFilterDisables(False)  # Show only files that match the filter
        
        # 2. Setup View
        self.tree_view = QTreeView(self)
        self.tree_view.setModel(self.model)
        w = self.width() - 20 # -20 for padding
        self.tree_view.setColumnWidth(0, int(w*0.6))  # Name
        self.tree_view.setColumnWidth(1, int(w*0.1))  # Size
        self.tree_view.setColumnWidth(2, int(w*0.1))  # Type
        if root_path:
            self.tree_view.setRootIndex(self.model.index(root_path))
        layout.addWidget(self.tree_view)
        
        # add context menu to create a new folder, delete a file/folder, and rename a file/folder
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.open_context_menu)
        # ------ Tree View Options ------
        ## 1. Sortable:
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder) # Name column ascending
        ## 2. Enable drag and drop
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDropIndicatorShown(True)
        self.tree_view.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self.tree_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.model.setReadOnly(False)
        ## 3. Enable multiple selection
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        # ------ ================= ------
        self.model.rootPathChanged.connect(lambda path: self.tree_view.setRootIndex(self.model.index(path)))
        
    def open_context_menu(self, position):
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return

        menu = QMenu()
        create_folder_action = menu.addAction("Create New Folder")
        delete_action = menu.addAction("Delete")
        rename_action = menu.addAction("Rename")
        check_action = menu.addAction("Check")
        uncheck_action = menu.addAction("Uncheck")

        action = menu.exec(self.tree_view.viewport().mapToGlobal(position))
        if action == create_folder_action:
            action_func = self.create_new_folder
        elif action == delete_action:
            action_func = self.delete_item
        elif action == rename_action:
            action_func = self.rename_item
        elif action == check_action:
            action_func = lambda idx: self.model.set_check_state(idx, Qt.CheckState.Checked)
        elif action == uncheck_action:
            action_func = lambda idx: self.model.set_check_state(idx, Qt.CheckState.Unchecked)
        else:
            return  # No action selected
        sel = self.tree_view.selectionModel().selectedIndexes()
        for idx in sel:
            action_func(idx)
            
    def create_new_folder(self, index: QModelIndex):
        # Get the path of the selected item (if it's a file, get its parent directory)
        dir_path = Path(self.model.filePath(index))
        if not dir_path.is_dir():
            dir_path = dir_path.parent

        # Prompt user for the new folder name
        folder_name, ok = QInputDialog.getText(self, "Create New Folder", "Folder name:")
        if ok and folder_name.strip():
            new_folder_path = dir_path / folder_name.strip()
            try:
                new_folder_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create folder:\n{str(e)}")

    def delete_item(self, index: QModelIndex):
        file_path = Path(self.model.filePath(index))
        is_dir = file_path.is_dir()

        item_type = "folder" if is_dir else "file"

        # Confirm deletion with the user
        reply = QMessageBox.question(
            self, 
            f"Delete {item_type.capitalize()}", 
            f"Are you sure you want to delete this {item_type}?\n{file_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if is_dir:
                    shutil.rmtree(file_path)  # Deletes folder and its contents
                else:
                    file_path.unlink()      # Deletes file
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete {item_type}:\n{str(e)}")

    def rename_item(self, index: QModelIndex):
        file_path = Path(self.model.filePath(index))
        old_name = file_path.name
        dir_path = file_path.parent

        # Prompt user for the new name
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if ok and new_name.strip() and new_name != old_name:
            new_path = Path(dir_path) / new_name.strip()
            try:
                new_path.rename(file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not rename item:\n{str(e)}")
    
    def get_checked_items(self)-> list[str]:
        """Return a list of file paths that are currently checked."""
        return [path for path, state in self.model.check_states.items() if state == Qt.CheckState.Checked]
