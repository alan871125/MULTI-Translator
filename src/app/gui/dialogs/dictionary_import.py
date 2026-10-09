from PySide6.QtWidgets import (
    QCheckBox, QDialog, QGroupBox, QVBoxLayout,
    QDialogButtonBox
)


class ImportDictionaryDialog(QDialog):
    """A dialog for importing a dictionary file into the current translation table."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Dictionary")
        layout = QVBoxLayout()
        self.setLayout(layout)
        # Initialize the Key Selection GroupBox and layout
        # checkboxes to select which columns to use as key:
        self.key_group = QGroupBox("Select Key Columns")
        self.key_layout = QVBoxLayout(self.key_group)
        for col in ['key', 'original', 'translation']:
            checkbox = QCheckBox(col)
            self.key_layout.addWidget(checkbox)
            if col == 'key':
                checkbox.setChecked(True)  # Default to using 'key' as the primary key column
        layout.addWidget(self.key_group)
        
        # Add OK, Cancel, and Reset buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    @property
    def keys(self) -> list[str]:
        """Returns a list of selected key columns."""
        return [cb.text() for cb in self.key_group.findChildren(QCheckBox) if cb.isChecked()]