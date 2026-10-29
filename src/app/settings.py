"""
This module defines the application settings and workspace management for the RPG Translator application.

We use Pydantic's BaseModel & BaseSettings instead of Qt's QSettings to provide:
1. type safety during development(static type checking) and
2. runtime setting value type validation
"""

from __future__ import annotations
import os
import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Literal, Annotated, ClassVar, TypeVar
from pydantic import BaseModel, model_validator, ConfigDict, Field, BeforeValidator, PlainSerializer
from pydantic_settings import BaseSettings, SettingsConfigDict

from PySide6.QtCore import QObject
from qt_extensions.core import TypedSignal

from core.setting_space import SettingSpace, SettingScope
from core.lru_file import LeastRecentlyUsedFiles

logger = logging.getLogger(__name__)

    
WORKSPACE_FILE_EXTENSION = ".translation-workspace"
DEFAULT_LOCAL_WORKSPACE_FILE= "./workspace.translation-workspace"

DEFAULT_WORKSPACE_NAME = "Default"
DEFAULT_WORKSPACE_DIR = "%CWD%"
DEFAULT_SETTINGS_FILE = "settings.json"
DEFAULT_GAME_DATA_DIR = "%WORKSPACE_DIR%/data"
DEFAULT_USER_DICT_DIR = "%WORKSPACE_DIR%/dictionary"
DEFAULT_OUTPUT_DIR = "%WORKSPACE_DIR%/output"
DEFAULT_DB_PATH = "%WORKSPACE_DIR%/user_dict.db"
DEFAULT_PLUGIN = "Simple JSON"

SupportedLanguages = Literal["en", 'zh-tw']
# Matches either %VAR% (group 1) OR $VAR / ${VAR} (group 2)
_VARPATTERN = re.compile(r'%(\w+|\{[^}]*\}?)%|\$(\w+|\{[^}]*\}?)')

@dataclass
class Confirmations:
    share_translation: bool = False

class AppSettings(SettingSpace):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    if TYPE_CHECKING:
        # A workaround to make the type checker understand that recent_files can be initialized with LeastRecentlyUsedFiles|list[str],
        # while at runtime it will always be a LeastRecentlyUsedFiles instance.
        def __init__( 
            self, *,
            recent_files: LeastRecentlyUsedFiles | Iterable[str] = ...,
            **kwargs: Any,
        ) -> None: ...
    class TranslationSettings(SettingSpace, BaseSettings):
        class RequestDelay(SettingSpace):
            google:  float = 0.3
            deepl:   float = 0.0
            custom:  float = 0.0
        class RequestConcurrency(SettingSpace):
            google:  int = 1
            deepl:   int = 5
            custom:  int = 5
        # use BaseSettings to load api keys from .env file
        model_config = SettingsConfigDict(extra="ignore", env_file=".env", env_file_encoding="utf-8")
        api_provider:     str = "google"
        custom_api_url:   str = "https://openrouter.ai/api/v1" 
        custom_api_model: str = "openrouter/free"
        custom_api_key: str|None = None
        deepl_api_key:  str|None = None
        source_lang: str = "auto"
        target_lang: str = "en"
        request_delay: RequestDelay = Field(default_factory=RequestDelay)
        request_concurrency: RequestConcurrency = Field(default_factory=RequestConcurrency)
        
        @property
        def api_key(self) -> str|None:
            """Return the API key for the selected provider."""
            if self.api_provider.lower() == "deepl":
                return self.deepl_api_key
            elif self.api_provider.lower() == "custom":
                return self.custom_api_key
            return None
        
        @api_key.setter
        def api_key(self, value: str|None)->None:
            """Set the API key for the selected provider."""
            if self.api_provider.lower() == "deepl":
                self.deepl_api_key = value
            elif self.api_provider.lower() == "custom":
                self.custom_api_key = value
        
    class UISettings(SettingSpace):
        # Theme and UI
        language: SupportedLanguages = "en"
        dark_mode: bool = False
        theme: str = "default"
        font_size: int = 11

    ui: UISettings = Field(default_factory=UISettings)
    translation: TranslationSettings = Field(default_factory=TranslationSettings)
    confirmations: Confirmations = Field(default_factory=Confirmations)
    plugin_settings:dict[str, object] = Field(default_factory=dict)
    max_workers: int = 4
    
    # Recent Files and Session
    restore_last_session: bool = True
    recent_files: Annotated[
        LeastRecentlyUsedFiles, 
            BeforeValidator(LeastRecentlyUsedFiles),
            PlainSerializer(lambda v: v.to_list())
    ] = Field(default_factory=LeastRecentlyUsedFiles)
    last_open_workspace: str|None = None  # Path to the last opened workspace, used for restoring session on startup
    last_open_tabs: list[str] = Field(default_factory=list)  # List of paths to the last opened tabs, used for restoring session on startup
    
    plugin:        str = DEFAULT_PLUGIN
    workspace_dir: str = DEFAULT_WORKSPACE_DIR
    game_data_dir: str = DEFAULT_GAME_DATA_DIR
    user_dict_dir: str = DEFAULT_USER_DICT_DIR
    output_dir:    str = DEFAULT_OUTPUT_DIR
    db_path:       str = DEFAULT_DB_PATH
    
    def save(self, path: str|Path=DEFAULT_SETTINGS_FILE, *, save_api_keys: bool = True):
        """Save the settings to a JSON file."""
        path = Path(path)
        settings_dict = self.model_dump(mode="json")
        api_keys = {}
        for k, v in settings_dict.items():
            if k.lower().endswith("_api_key"):
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
    
class Workspace(BaseModel):
    FILE_EXTENSION: ClassVar[str] = ".multi-workspace"
    name: str | None = None
    settings: dict = Field(default_factory=dict)
    _workspace_file: Path|None = None  # Path to the workspace file, used for saving local settings
    
    @model_validator(mode="after")
    def validate_settings(self):
        if self.settings.get("restore_last_session"):
            # initialize last_open_tabs, so that the local settings can intercept it when saving the workspace
            self.settings.setdefault("last_open_tabs", [])
        else:
            self.settings.pop("last_open_tabs", None)
        return self
    
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
                return cls(name=name, settings={"workspace_dir": path.as_posix()}, _workspace_file=workspace_file)
        if not path.suffix == cls.FILE_EXTENSION:
            logger.warning(
                f"Workspace file {path} does not have the expected extension {cls.FILE_EXTENSION}."
                "Loading anyway"
            )
        obj =  cls.model_validate_json(path.read_text(encoding="utf-8"))
        obj._workspace_file = path
        return obj
    
    def save(self, path: str|Path):
        """Save workspace to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4, ensure_ascii=False))
        logger.info(f"Workspace saved to {path}")
    
# The typing inheritance trick: `SettingsData if TYPE_CHECKING else object`
# tricks the type checker into thinking that Settings inherits from SettingsData, 
# while at runtime it inherits from QObject. 
# This allows us to use Settings as if it were a subclass of SettingsData for type checking purposes.
class Settings(QObject, AppSettings if TYPE_CHECKING else object):
    """A wrapper around SettingsData that provides signal support for PySide6."""
    setting_changed:   TypedSignal[str] = TypedSignal(str)
    workspace_changed: TypedSignal[str] = TypedSignal(str)
    _workspace_path: Path|None = None  # Path to the current workspace file, used for saving local settings
    _workspace_name: str|None = None  # Name of the current workspace, used for saving local settings
    def __init__(self, global_settings:AppSettings|dict[str,Any]|None=None, *, local_settings:dict[str, Any]|None=None, parent:QObject|None=None, **overrides):
        """
        Arguments:
            global_settings (SettingsData|dict[str,Any]|None): The global settings to use. If None, defaults will be used.
            local_settings (dict[str, Any]|None): Local settings that override global settings.
            parent (QObject|None): The parent object.
            **overrides: Field values that take precedence over `global_settings`. Updates the global settings with these values.
        """
        
        super().__init__(parent)
        if isinstance(global_settings, AppSettings):
            self._space:AppSettings = global_settings
            self._space.update(**overrides)
        else:
            self._space:AppSettings = AppSettings(**global_settings or {}, **overrides)
        if local_settings:
            self._space.update(**local_settings, scope=SettingScope.LOCAL)

    if not TYPE_CHECKING: # A typing trick to make the type checker understand that accessing unrecognized attributes will raise an AttributeError
        def __getattr__(self, name: str):
            if name.startswith("_"):
                raise AttributeError(name)
            if name in type(self._space).model_fields or hasattr(self._space, name):
                value = getattr(self._space, name)
                if name.endswith("_dir") or name.endswith("_path"):
                    return self._translate_path(value)
                return value
            raise AttributeError(f"{type(self).__name__} object has no attribute '{name}'")
    
    @classmethod
    def load(cls, path: str|Path):
        """Load settings from a JSON file."""
        path = Path(path)
        return cls(global_settings=AppSettings.load(path))

    def _translate_path(self, path: str) -> str:
        """Translate a path that may contain placeholders 
        - %WORKSPACE_DIR%: Directory of the current local workspace (cwd if None)
        - %CWD%: Current working directory (where the app is launched from)
        """
        cwd = os.getcwd()
        
        # 1. Safely resolve workspace_dir first using only CWD (prevents recursion)
        raw_ws_dir = self.get_raw("workspace_dir", DEFAULT_WORKSPACE_DIR)
        
        ws_var_map = {"CWD": cwd}
        def replace_ws_var(match: re.Match[str]) -> str:
            var_name = (match.group(1) or match.group(2)).upper()
            if var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            return ws_var_map.get(var_name, match.group(0))
            
        resolved_ws_dir = os.path.expandvars(raw_ws_dir)
        resolved_ws_dir = re.sub(_VARPATTERN, replace_ws_var, resolved_ws_dir)
        resolved_ws_dir = Path(resolved_ws_dir).as_posix()

        # 2. Build the full variable map using the resolved workspace directory
        var_map = ws_var_map.copy()|{"WORKSPACE_DIR": resolved_ws_dir}
        
        def replace_var(match: re.Match[str]) -> str:
            # Group 1 is for %var%, Group 2 is for $var / ${var}
            var_name = match.group(1) or match.group(2)
            if var_name.startswith("{") and var_name.endswith("}"):
                var_name = var_name[1:-1]
            var_name = var_name.upper()
            return var_map.get(var_name, match.group(0))
            
        path = os.path.expandvars(path)  # Expand environment variables if any
        path = re.sub(_VARPATTERN, replace_var, path)
        return Path(path).as_posix()
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name in ["data", "settings_changed"]:
            return super().__setattr__(name, value)
        try:
            self.set_val(name, value)
            self.setting_changed.emit(name)
            if name == "workspace_dir":
                self.workspace_changed.emit(name)
        except:
            raise AttributeError(f"'Settings' object has no attribute '{name}'")
        
    def __setitem__(self, name: str, value: Any) -> None:
        """Allow dict-like access to settings."""
        try:
            self.set_val(name, value)
        except AttributeError:
            raise KeyError(f"{name} not found in Settings.")
        
    def __getitem__(self, name: str) -> Any:
        """Allow dict-like access to settings."""
        space = self._space
        try:
            for part in name.split("."): # traverse to the target SettingSpace
                space = getattr(space, part)
            return space
        except AttributeError:
            raise KeyError(f"{name} not found in Settings.")

    T = TypeVar("T")
    def get_raw(self, key: str,/, default: T|None = None, scope:SettingScope|None=None) -> Any|T:
        """
        Get the raw value of a setting without post-processing (e.g., path translation).
        """
        *parts, last_part = key.split(".")
        space = self._space
        for part in parts: # traverse to the target SettingSpace
            space = getattr(space, part)
        if scope == SettingScope.LOCAL:
            return space.get_local(last_part, default)
        elif scope == SettingScope.GLOBAL:
            return space.get_global(last_part, default)
        return space.get(last_part, default)
    
    def set_val(self, key, value: Any, scope:SettingScope|None=None):
        """Set the value of a setting, either globally or locally."""
        *parts, last_part = key.split(".")
        space = self._space
        for part in parts: # traverse to the target SettingSpace
            space = space.get(part)
        space.update_val(last_part, value, scope=scope)
        self.setting_changed.emit(key)
            
    @property
    def workspace_name(self):
        if self._workspace_name is not None:
            return self._workspace_name
        return Path(self.workspace_dir).name
    
    @property
    def workspace_path(self):
        return self._workspace_path or Path(self.workspace_dir)/f"{self.workspace_name}{Workspace.FILE_EXTENSION}"
    
    def save(self, path: str|Path=DEFAULT_SETTINGS_FILE, *, save_api_keys: bool = True):
        """Save the global settings to a JSON file."""
        self._space.save(path, save_api_keys=save_api_keys)
        Workspace(name=self.workspace_name, settings=self.get_local_settings()).save(self.workspace_path)
        
    def update(self, **overrides):
        self._space.update(**overrides)
        self.setting_changed.emit("*")  # Emit a signal indicating that all settings have changed

    def update_local(self, **overrides):
        """Update local settings with new values."""
        for key, value in overrides.items():
            if key in AppSettings.model_fields:
                self._local[key] = value
                self.setting_changed.emit(key)
            else:
                logger.warning(f"Attempted to update unknown local setting '{key}'.")

    def load_workspace(self, path: str|Path):
        """Load local settings from a JSON file."""
        path = Path(path)
        if path.is_file():
            self._workspace_path = path
        if path.is_dir() and (path / f"{path.name}{Workspace.FILE_EXTENSION}").is_file():
            path = path / f"{path.name}{Workspace.FILE_EXTENSION}"
        workspace = Workspace.load(path)
        self._workspace_name = workspace.name
        self._space.update(**workspace.settings, scope=SettingScope.LOCAL)
        self.setting_changed.emit("*")
        self.workspace_changed.emit("*")
            
    def load_update(self, path: str|Path):
        """Load settings from a JSON file and update the current settings."""
        updates = AppSettings.load(path).model_dump()
        new = self._space.model_validate({**self._space.model_dump(), **updates})
        self._space = new
        self.setting_changed.emit("*")  # Emit a signal indicating that all settings have changed
    
    def add_recent_file(self, file_path: str|Path):
        """Add a file to the recent files list."""
        self._space.recent_files.add_recent_file(file_path)
        self.setting_changed.emit("recent_files")
    
    def reset(self, name: str|None=None):
        """Reset a specific setting or all settings to their default values."""
        raise NotImplementedError("Resetting settings is not implemented yet.")
    
    def is_local(self, key:str) -> bool:
        """Check if a setting is defined in the local settings."""
        *parts, last_part = key.split(".")
        space = self._space
        for part in parts: # traverse to the target SettingSpace
            space = getattr(space, part)
        return last_part in space._local
    
    def get_local_keys(self) -> set[str]:
        """Return a set of all local setting keys."""
        local_keys = set()
        def collect_local_keys(space: SettingSpace, prefix: tuple = ()):
            for key in space._local.keys():
                local_keys.add(".".join(prefix + (key,)))
            for key, value in space:
                if isinstance(value, SettingSpace):
                    collect_local_keys(value, prefix=prefix + (key,))
        collect_local_keys(self._space)
        return local_keys
    
    def get_local_settings(self, flatten = False) -> dict[str, Any]:
        """Return a dictionary of all local settings."""
        local_settings = {}
        def collect_local_settings_flat(space: SettingSpace, prefix: tuple = ()):
            for key, value in space._local.items():
                local_settings[".".join(prefix + (key,))] = value
            for key, value in space:
                if isinstance(value, SettingSpace):
                    collect_local_settings_flat(value, prefix=prefix + (key,))
        def collect_local_settings_nested(space: SettingSpace) -> dict[str, Any]:
            result = {}
            for key, value in space._local.items():
                result[key] = value
            for key, value in space:
                if not isinstance(value, SettingSpace):
                    continue
                if nested:=collect_local_settings_nested(value):
                    result[key] = nested
            return result
        if flatten:
            collect_local_settings_flat(self._space)
        else:
            local_settings = collect_local_settings_nested(self._space)
        return local_settings