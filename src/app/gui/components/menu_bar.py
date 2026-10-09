import logging
from PySide6.QtWidgets import QMenu

from core.lru_file import LeastRecentlyUsedFiles
from qt_extensions.core import TypedSignal
from ..menu_utils import initialize_menu

logger = logging.getLogger(__name__)

class RecentFilesMenu(QMenu):
    """Custom QMenu to handle Recent Files with dynamic content."""
    recent_file_selected = TypedSignal(str)
    def __init__(self, title, lru_files:LeastRecentlyUsedFiles, parent=None):
        super().__init__(title, parent)
        self.lru_files = lru_files
        self.refresh()
        
    def refresh(self, _:str|None=None):
        self.clear()
        dir_def, file_def = {}, {}
        # use `$n:` as a special prefix before file paths in the menu definition 
        # to indicate that the menu item should use the file path as its name.
        for path in self.lru_files.iter(reverse=True):
            path_str = path.as_posix()
            if path.is_dir() or path.suffix == ".translation-workspace":
                dir_def['$n:' + path_str] = lambda _, p=path_str: self.recent_file_selected.emit(p)
            else:
                file_def['$n:' + path_str] = lambda _, p=path_str: self.recent_file_selected.emit(p)
        
        recent_files_def = dir_def|{'$n:separator1': '$separator'}|file_def
        initialize_menu(
            menu_def=recent_files_def, 
            root_menu=self, 
            root_menu_name="file.recentFiles", 
            tr=lambda x: x
        )
        
        
