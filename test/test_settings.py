
import pytest
from pathlib import Path
from app.settings import Settings

class TestSettings:
    def test_init(self):
        settings = Settings()
        assert settings._global is not None
        assert not bool(settings._local) # The local settings should be empty by default

    def test_init_with_local_settings(self):
        local_settings = {"plugin": "Simple JSON"}
        settings = Settings(plugin='RPG Maker MZ', local_settings=local_settings)
        assert settings._local == local_settings
        assert settings.plugin == "Simple JSON"  # Local settings should override global settings

    def test_attribute_get(self):
        settings = Settings(api_provider="Google", source_lang="auto", plugin="RPG Maker MV")
        # Test access to SettingsData attributes through Settings
        assert settings.api_provider == "Google"
        assert settings.source_lang == "auto"
        assert settings.plugin == "RPG Maker MV"
        assert settings._global.output_dir == "%WORKSPACE_DIR%/output" # this is the raw value
        # %WORKSPACE_DIR% defaults to cwd if not set, so the normalized value should be the cwd/output
        assert settings.output_dir ==  Path('output').resolve().as_posix() # this is the normalized value

    def test_attribute_set(self):
        settings = Settings(api_provider="DeepL", plugin="RPG Maker MZ")
        assert settings._global.api_provider == "DeepL"
        assert settings.api_provider == "DeepL"
        settings.api_provider = "Google"
        assert settings._global.api_provider == "Google"
        assert settings.api_provider == "Google"

    def test_signals(self):
        settings = Settings()
        emitted_settings = []
        def foo(v):
            print(f"Setting changed: {v}")
            emitted_settings.append(v)
        settings.setting_changed.connect(foo)
        
        settings.api_provider = "DeepL"
        settings.plugin = "Simple JSON"
        assert emitted_settings == ["api_provider", "plugin"], "Signals should be emitted for each setting change."

    def test_invalid_attribute(self):
        settings = Settings()    
        with pytest.raises(AttributeError):
            _ = settings.non_existent_attribute  # type: ignore -> We know this does't exist, let the static type checker be quite
        
        with pytest.raises(AttributeError):
            settings.non_existent_attribute = "value"

    def test_getitem_setitem(self):
        settings = Settings()
        
        # getitem
        assert settings["api_provider"] == "Google"
        
        # setitem
        settings["api_provider"] = "DeepL"
        assert settings.api_provider == "DeepL"
        
        with pytest.raises(KeyError):
            _ = settings["non_existent"]
        
        with pytest.raises(KeyError):
            settings["non_existent"] = "value"
