import logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QTabWidget, QTableView, QAbstractItemView

from app.settings import Settings
from .console_widget import ConsoleWidget

logger = logging.getLogger(__name__)

from .data_tree_view import CheckableFileExplorer
class SuggestionsTableView(QTableView):
    """
    A placeholder widget for fuzzy suggestions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Use row selection and single selection so a row is selected at a time
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h_header = self.horizontalHeader()
        h_header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        h_header.setStretchLastSection(True)
class BottomPanel(QTabWidget):
    """
    Bottom panel containing Dictionary and Fuzzy Matching tools.
    """
    def __init__(self, language_pack, settings:Settings, parent:QWidget|None=None):
        super().__init__(parent)
        self.L = language_pack
        self.settings = settings
        self.init_ui()
        self.setMovable(True)
        
    def init_ui(self):
        # Dictionary Tab
        Path(self.settings.user_dict_dir).mkdir(parents=True, exist_ok=True)  # Ensure the user dictionary directory exists
        self.dict_tab = CheckableFileExplorer(root_path=self.settings.user_dict_dir, name_filters=["*.csv"])
        self.addTab(self.dict_tab, self.L["bottom_tab.dictionary"])

        # Fuzzy Suggestions Tab
        self.fuzzy_tab = QWidget()
        fuzzy_layout = QVBoxLayout(self.fuzzy_tab)
        fuzzy_layout.addWidget(QLabel("Fuzzy suggestions will go here"))
        self.addTab(self.fuzzy_tab, self.L["bottom_tab.fuzzy_suggestions"])
        
        self.console_tab = QWidget()
        console_layout = QVBoxLayout(self.console_tab)
        self.console_widget = ConsoleWidget()
        console_layout.addWidget(self.console_widget)
        self.addTab(self.console_tab, self.L["bottom_tab.console"])

    def refresh(self, cell_data=None):
        """
        Refresh the panel content based on the currently selected cell.
        """
        logger.debug(f"Refreshing bottom panel with data: {cell_data}")
        # Logic to update dictionary and fuzzy matching based on cell_data goes here
