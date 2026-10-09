
import pytest
from app.settings import Settings, SettingsData, WorkspaceData
def test_settings_initialization():
    # This should not raise RecursionError
    settings = Settings()
    assert settings.data is not None
    assert settings.workspace_data is not None

def test_settings_attribute_access():
    settings = Settings()
    # Test access to SettingsData attributes via proxy
    assert settings.API == "Google"
    assert settings.SOURCE_LANG == "auto"
    
    # Test access to WorkspaceData attributes via proxy
    assert settings.engine == "RPG Maker MV"
    assert settings.output_dir == "output" # this is the normalized value
    assert settings.workspace_data.output_dir == "./output"

def test_settings_attribute_setting():
    settings = Settings()
    
    # Set SettingsData attribute
    settings.API = "DeepL"
    assert settings.data.API == "DeepL"
    assert settings.API == "DeepL"
    
    # Set WorkspaceData attribute
    settings.engine = "Simple JSON"
    assert settings.workspace_data.engine == "Simple JSON"
    assert settings.engine == "Simple JSON"

def test_settings_signals():
    settings = Settings()
    emitted_settings = []
    emitted_workspaces = []
    
    settings.setting_changed.connect(lambda x: emitted_settings.append(x))
    settings.workspace_changed.connect(lambda x: emitted_workspaces.append(x))
    
    settings.API = "DeepL"
    assert "API" in emitted_settings
    
    settings.engine = "Simple JSON"
    assert "engine" in emitted_workspaces

def test_settings_invalid_attribute():
    settings = Settings()
    with pytest.raises(AttributeError):
        _ = settings.non_existent_attribute # type: ignore -> We know this does't exist, let the static type checker be quite
    
    with pytest.raises(AttributeError):
        settings.non_existent_attribute = "value"

def test_settings_getitem_setitem():
    settings = Settings()
    
    # getitem
    assert settings["API"] == "Google"
    
    # setitem
    settings["API"] = "DeepL"
    assert settings.API == "DeepL"
    
    with pytest.raises(KeyError):
        _ = settings["non_existent"]
    
    with pytest.raises(KeyError):
        settings["non_existent"] = "value"
