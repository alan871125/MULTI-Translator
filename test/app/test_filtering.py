from pytestqt.qt_compat import qt_api

class TestTableFilters:
    
    def test_button_toggles_update_filters(self, qtbot):
        """Test that the LevelFilterButtons correctly updates the TableFilters when buttons are toggled"""
        from app.gui.components.top_bar import LevelFilterButtons
        from app.models.filters import TableFilters
        from core.translation import TranslationLevel

        filters = TableFilters()
        buttons = LevelFilterButtons(filters)
        qtbot.addWidget(buttons)

        # Initially, all levels should be True
        assert all(filters.levels.values())

        # Toggle the "VERIFIED" button off
        btn_verified = buttons.buttons.buttons()[TranslationLevel.VERIFIED.value-1]
        qtbot.mouseClick(btn_verified, qt_api.QtCore.Qt.LeftButton)
    
    def test_search_dialog_integration(self, qtbot):
        from app.gui.dialogs.search import SearchDialog, SearchLineEdit
        from app.models.filters import TableFilters, ColumnFilter
        from core.translation import TranslationLevel

        filters = TableFilters()
        dialog = SearchDialog(filters)
        qtbot.addWidget(dialog)

        # fill in the search dialog with some test data
        entry: SearchLineEdit= dialog.filter_entries['original']['entry']
        entry.setText("test1")
        entry.returnPressed.emit()
        dialog.set_filters()  # Apply the filters to the TableFilters instance
        
        # Check that the filter was added
        assert 'original' in filters.filters
        _filter: ColumnFilter = filters.filters['original']
        assert _filter == ColumnFilter(column='original', text='test1', is_regex=False, match_case=False)
        
        # toggle is_regex and match_case button
        is_regex_btn = entry.buttons['regex']
        match_case_btn = entry.buttons['case']
        qtbot.mouseClick(is_regex_btn, qt_api.QtCore.Qt.LeftButton)
        qtbot.mouseClick(match_case_btn, qt_api.QtCore.Qt.LeftButton)
        dialog.set_filters()  # Apply the filters to the TableFilters instance
        _filter: ColumnFilter = filters.filters['original']
        assert _filter.is_regex and _filter.match_case
        