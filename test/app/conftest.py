import pytest
from pathlib import Path
from app.presenter import TranslationAppPresenter
from app.settings import Settings, AppSettings
from app.models.session import TranslationSession
from app.gui.main_window import TranslationApp
@pytest.fixture(scope="session")
def tmp_workspace_dir(tmp_path_factory: pytest.TempPathFactory):
    """Create a temporary workspace directory for testing."""
    tmp_dir = tmp_path_factory.mktemp("workspace")
    return tmp_dir

@pytest.fixture(scope="session")
def tmp_settings(tmp_workspace_dir:Path):
    """Create a Settings instance with the temporary workspace directory."""
    app_settings = AppSettings(
        workspace_dir=tmp_workspace_dir.as_posix()
    )
    return Settings(app_settings)

@pytest.fixture(scope="session")
def session(tmp_settings: Settings)->TranslationSession:
    """Create a TranslationSession instance for testing."""
    return TranslationSession(settings=tmp_settings)

@pytest.fixture
def main_window(qtbot, tmp_settings: Settings) -> TranslationApp:
    """Instantiates the main window and registers it with qtbot."""
    window = TranslationApp(tmp_settings)
    qtbot.addWidget(window)
    return window

@pytest.fixture
def presenter(main_window: TranslationApp, tmp_settings: Settings, session:TranslationSession) -> TranslationAppPresenter:
    """Creates a connected Presenter instance."""
    return TranslationAppPresenter(
        main_window=main_window,
        settings=tmp_settings,
        session=session,
        translation_tab_widget=main_window.translation_table,
    )
    