from __future__ import annotations
import json
import logging
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Literal, Annotated, ClassVar, TypeVar
from pydantic import Field, BeforeValidator, PlainSerializer, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from PySide6.QtCore import QObject
from qt_extensions.core import TypedSignal

from core.lru_file import LeastRecentlyUsedFiles

logger = logging.getLogger(__name__)

SupportedLanguages = Literal["en", 'zh-tw']
    
WORKSPACE_FILE_EXTENSION = ".translation-workspace"
GLOBAL_WORKSPACE_FILE = "%CWD%/global.translation-workspace"
DEFAULT_LOCAL_WORKSPACE_FILE= "./workspace.translation-workspace"

DEFAULT_WORKSPACE_NAME = "Default"
DEFAULT_WORKSPACE_DIR = "%CWD%"
DEFAULT_SETTINGS_FILE = "settings.json"
DEFAULT_GAME_DATA_DIR = "%WORKSPACE_DIR%/data"
DEFAULT_USER_DICT_DIR = "%WORKSPACE_DIR%/dictionary"
DEFAULT_OUTPUT_DIR = "%WORKSPACE_DIR%/output"
DEFAULT_DB_PATH = "%WORKSPACE_DIR%/user_dict.db"
DEFAULT_PLUGIN = "Simple Json"    

@dataclass
class Confirmations:
    share_translation: bool = False

class SettingsData(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", env_file=".env", env_file_encoding="utf-8")
    if TYPE_CHECKING:
        # A workaround to make the type checker understand that recent_files can be initialized with LeastRecentlyUsedFiles|list[str],
        # while at runtime it will always be a LeastRecentlyUsedFiles instance.
        def __init__( 
            self, *,
            recent_files: LeastRecentlyUsedFiles | Iterable[str] = ...,
            **kwargs: Any,
        ) -> None: ...

    source_lang: str = "auto"
    target_lang: str = "en"
    
    # Them and UI
    language: SupportedLanguages = "en"
    dark_mode: bool = False
    theme: str = "default"
    font_size: int = 11
    
    # Recent Files and Session
    restore_last_session: bool = True
    recent_files: Annotated[
    LeastRecentlyUsedFiles, 
        BeforeValidator(LeastRecentlyUsedFiles),
        PlainSerializer(lambda v: v.to_list())
    ] = Field(default_factory=LeastRecentlyUsedFiles)
    last_open_workspace: str|None = None  # Path to the last opened workspace, used for restoring session on startup
    last_open_tabs: list[str] = Field(default_factory=list)  # List of paths to the last opened tabs, used for restoring session on startup
    
    workspace_dir: str = DEFAULT_WORKSPACE_DIR
    game_data_dir: str = DEFAULT_GAME_DATA_DIR
    user_dict_dir: str = DEFAULT_USER_DICT_DIR
    output_dir:    str = DEFAULT_OUTPUT_DIR
    plugin:        str = DEFAULT_PLUGIN
    db_path:       str = DEFAULT_DB_PATH
    
    # Translation API Settings
    api_provider:     str = "Google"
    custom_api_url:   str = "https://openrouter.ai/api/v1" 
    custom_api_model: str = "openrouter/free"
    # openrouter_api_key: str|None = None
    # google_api_key:     str|None = None
    deepl_api_key:      str|None = None
    custom_api_key:     str|None = None
    
    # Other Settings
    confirmations: Confirmations = Field(default_factory=Confirmations)
    plugin_settings:dict[str, object] = Field(default_factory=dict)
    max_workers: int = 4
    
    def save(self, path: str|Path=DEFAULT_SETTINGS_FILE, *, save_api_keys: bool = True):
        """Save the settings to a JSON file."""
        path = Path(path)
        settings_dict = self.model_dump(mode="json")
        api_keys = {}
        for k, v in settings_dict.items():
            if k.endswith("_api_key") and v is None:
                api_keys[k] = v
        for k in api_keys:
            settings_dict.pop(k)
        if api_keys and save_api_keys:
            # TODO: Increase security by encrypting or using keyring
            env_path = path.parent/'.env'
            import dotenv
            for k, v in api_keys.items():
                dotenv.set_key(env_path, k.upper(), v)
            logger.info(f"API keys saved to {env_path}. Please ensure this file is secured.")
        try:
            with open(path, "w") as f:
                json.dump(settings_dict,  f, ensure_ascii=False, indent=4)
            logger.info(f"Settings saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save settings to {path}: {e}")
        
    @classmethod
    def load(cls, path: str|Path):
        """Load settings from a JSON file."""
        path = Path(path)
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
    
    def update(self, **kwargs):
        """Update settings with new values."""
        for key, value in kwargs.items():
            if key in self.__class__.model_fields:
                setattr(self, key, value)
            else:
                logger.warning(f"Attempted to update unknown setting '{key}'.")

class Workspace(BaseModel):
    FILE_EXTENSION: ClassVar[str] = ".multi-workspace"
    name: str | None = None
    settings: dict = Field(default_factory=dict)
    @classmethod
    def load(cls, path: str|Path):
        """Load workspace from a JSON file."""
        path = Path(path)
        if path.is_dir():
            name = path.name
            # If the path is a directory, look for a workspace file inside it
            workspace_file = path / f"{name}{cls.FILE_EXTENSION}"
            if workspace_file.is_file():
                path = workspace_file
            else:
                logger.warning(
                    f"Workspace directory {path} does not contain a workspace file named {name}{cls.FILE_EXTENSION}. "
                    "Loading with default settings."
                )
                return cls(name=name, settings={})
        if not path.suffix == cls.FILE_EXTENSION:
            logger.warning(
                f"Workspace file {path} does not have the expected extension {cls.FILE_EXTENSION}."
                "Loading anyway"
            )
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
    
# The typing inheritance trick: `SettingsData if TYPE_CHECKING else object`
# tricks the type checker into thinking that Settings inherits from SettingsData, 
# while at runtime it inherits from QObject. 
# This allows us to use Settings as if it were a subclass of SettingsData for type checking purposes.
class Settings(QObject, SettingsData if TYPE_CHECKING else object):
    """A wrapper around SettingsData that provides signal support for PySide6."""
    setting_changed:   TypedSignal[str] = TypedSignal(str)
    workspace_changed: TypedSignal[str] = TypedSignal(str)
    def __init__(self, global_settings:SettingsData|dict[str,Any]|None=None, *, local_settings:dict[str, Any]|None=None, parent:QObject|None=None, **overrides):
        """
        Arguments:
            global_settings (SettingsData|dict[str,Any]|None): The global settings to use. If None, defaults will be used.
            local_settings (dict[str, Any]|None): Local settings that override global settings.
            parent (QObject|None): The parent object.
            **overrides: Field values that take precedence over `global_settings`. Updates the global settings with these values.
        """
        
        super().__init__(parent)
        if isinstance(global_settings, SettingsData):
            self._global:SettingsData = global_settings
            self._global.update(**overrides)
        else:
            self._global:SettingsData = SettingsData(**global_settings or {}, **overrides)
        self._local:dict[str, Any] = local_settings or {}
    
    class SettingsSource(Enum):
        GLOBAL = auto()
        LOCAL  = auto()
        
    if not TYPE_CHECKING: # A typing trick to make the type checker understand that accessing unrecognized attributes will raise an AttributeError
        def __getattr__(self, name: str):
            if name.startswith("_"):
                raise AttributeError(name)
            if name in type(self._global).model_fields or hasattr(self._global, name):
                local = self._local.get(name)
                value = local if local is not None else getattr(self._global, name)
                if name.endswith("_dir") or name.endswith("_path"):
                    return self._translate_path(value)
                return value
            raise AttributeError(f"'Settings' object has no attribute '{name}'")
    
    @classmethod
    def load(cls, path: str|Path):
        """Load settings from a JSON file."""
        path = Path(path)
        return cls(global_settings=SettingsData.load(path))

    def _translate_path(self, path: str) -> str:
        """Translate a path that may contain placeholders 
        - %WORKSPACE_DIR%: Directory of the current local workspace (cwd if None)
        - %CWD%: Current working directory (where the app is launched from)
        """
        if isinstance(path, str):
            path = path.replace("%WORKSPACE_DIR%", self._global.workspace_dir)
            path = path.replace("%CWD%", str(Path.cwd()))
        return Path(path).as_posix()
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name in ["data", "settings_changed"]:
            super().__setattr__(name, value)
        elif name in SettingsData.model_fields:
            setattr(self._global, name, value)
            self.setting_changed.emit(name)
            if name == "workspace_dir":
                self.workspace_changed.emit(value)
        else:
            raise AttributeError(f"'Settings' object has no attribute '{name}'")
        
    def __setitem__(self, name: str, value: Any) -> None:
        """Allow dict-like access to settings."""
        try:
            setattr(self, name, value)
        except AttributeError:
            raise KeyError(f"{name} not found in SettingsData.")
        
    def __getitem__(self, name: str) -> Any:
        """Allow dict-like access to settings."""
        try:
            return getattr(self, name)
        except AttributeError:
            raise KeyError(f"{name} not found in SettingsData.")


    T = TypeVar("T")
    def get_raw(self, name: str,/, default: T|None = None, source:SettingsSource|None=None) -> Any|T:
        """
        Get the raw value of a setting without post-processing (e.g., path translation).
        """
        if source == self.SettingsSource.LOCAL:
            return self._local.get(name, default)
        elif source == self.SettingsSource.GLOBAL:
            return getattr(self._global, name, default)
        return self._local.get(name, getattr(self._global, name, default))
    
    @property
    def workspace_name(self):
        return  Path(self.workspace_dir).name
        
    def save(self, path: str|Path=DEFAULT_SETTINGS_FILE, *, save_api_keys: bool = True):
        """Save the global settings to a JSON file."""
        self._global.save(path, save_api_keys=save_api_keys)
        
    def update(self, **overrides):
        self._global.update(**overrides)
        self.setting_changed.emit("*")  # Emit a signal indicating that all settings have changed

    def update_local(self, **overrides):
        """Update local settings with new values."""
        for key, value in overrides.items():
            if key in SettingsData.model_fields:
                self._local[key] = value
                self.setting_changed.emit(key)
            else:
                logger.warning(f"Attempted to update unknown local setting '{key}'.")

    def load_workspace(self, path: str|Path):
        """Load local settings from a JSON file."""
        workspace = Workspace.load(path)
        # Replace the current local settings with the loaded workspace settings
        self._local = workspace.settings
            
    def load_update(self, path: str|Path):
        """Load settings from a JSON file and update the current settings."""
        updates = SettingsData.load(path).model_dump()
        new = self._global.model_validate({**self._global.model_dump(), **updates})
        self._global = new
        self.setting_changed.emit("*")  # Emit a signal indicating that all settings have changed
    
    def add_recent_file(self, file_path: str|Path):
        """Add a file to the recent files list."""
        self._global.recent_files.add_recent_file(file_path)
        self.setting_changed.emit("recent_files")
    
    def reset(self, name: str|None=None):
        """Reset a specific setting or all settings to their default values."""
        if name is None:
            self._global = SettingsData()
            self._local.clear()
            self.setting_changed.emit("*")  # Emit a signal indicating that all settings have changed
        elif name in SettingsData.model_fields:
            default_value = SettingsData.model_fields[name].default
            setattr(self._global, name, default_value)
            if name in self._local:
                del self._local[name]
            self.setting_changed.emit(name)
        else:
            raise AttributeError(f"'Settings' object has no attribute '{name}'")