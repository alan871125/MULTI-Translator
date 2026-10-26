import pytest
from pathlib import Path
from app.settings import Settings

WORKSPACE_EXAMPLE = """{
    "name": "Example Workspace",
    "settings":{
        "translation": {
            "api_provider": "deepl",
            "source_lang": "jp",
            "target_lang": "zh-TW"
        },
        "ui": {
            "language": "zh-TW"
        },
        "plugin": "RPG Maker MV"
    }   
}
"""

class TestSettings:
    def test_init(self):
        settings = Settings()
        assert settings._space is not None
        assert not bool(settings.get_local_keys()) # The local settings should be empty by default

    def test_init_with_local_settings(self):
        local_settings = {"plugin": "Simple JSON"}
        settings = Settings(plugin='RPG Maker MZ', local_settings=local_settings)
        assert settings._space._local == local_settings
        assert settings.plugin == "Simple JSON"  # Local settings should override global settings

    def test_attribute_get(self):
        settings = Settings(api_provider="google", source_lang="auto", plugin="RPG Maker MV")
        # Test access to SettingsData attributes through Settings
        assert settings.translation.api_provider == "google"
        assert settings.translation.source_lang == "auto"
        assert settings.plugin == "RPG Maker MV"
        assert settings._space.output_dir == "%WORKSPACE_DIR%/output" # this is the raw value
        # %WORKSPACE_DIR% defaults to cwd if not set, so the normalized value should be the cwd/output
        assert settings.output_dir ==  Path('output').resolve().as_posix() # this is the normalized value

    def test_attribute_set(self):
        settings = Settings({
            "translation":{
                "api_provider":"deepl", 
                "plugin":"RPG Maker MZ"
            }
        })
        assert settings.translation.api_provider == "deepl"
        settings.set_val("translation.api_provider", "google")
        assert settings.translation.api_provider == "google"

    def test_signals(self):
        settings = Settings()
        emitted_settings = []
        def foo(v):
            print(f"Setting changed: {v}")
            emitted_settings.append(v)
        settings.setting_changed.connect(foo)
        
        settings.set_val("translation.api_provider", "deepl")
        settings.set_val("plugin", "Simple JSON")
        assert emitted_settings == ["translation.api_provider", "plugin"], "Signals should be emitted for each setting change."

    def test_settings_invalid_attribute(self):
        settings = Settings()
        with pytest.raises(AttributeError):
            _ = settings.non_existent_attribute # type: ignore -> We know this does't exist, let the static type checker be quite
        
        with pytest.raises(AttributeError):
            settings.non_existent_attribute = "value"

    def test_getitem_setitem(self):
        settings = Settings()
        
        # getitem
        assert settings["translation.api_provider"] == "google"
        
        # setitem
        settings["translation.api_provider"] = "deepl"
        assert settings.translation.api_provider == "deepl"
        
        with pytest.raises(KeyError):
            _ = settings["non_existent"]
        
        with pytest.raises(KeyError):
            settings["non_existent"] = "value"

    
    def test_worksapce_settings(self):
        import tempfile
        settings = Settings()
        assert settings.workspace_name == Path.cwd().name  # default workspace name
        assert settings.plugin == "Simple Json"  # default plugin
        assert settings.translation.api_provider == "google"  # default translation provider
        assert settings.translation.source_lang == "auto"  # default source language
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as tmpfile:
            tmpfile.write(WORKSPACE_EXAMPLE)
            tmpfile_path = tmpfile.name
        settings.load_workspace(tmpfile_path)
        assert settings.workspace_name == "Example Workspace"
        assert settings.plugin == "RPG Maker MV"
        assert settings.translation.api_provider == "deepl"
        assert settings.translation.source_lang == "jp"

        assert settings.get_local_keys() == {
            "translation.api_provider",
            "translation.source_lang",
            "translation.target_lang",
            "ui.language",
            "plugin"
        }
if __name__ == "__main__":
    pytest.main([__file__])