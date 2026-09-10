import os
import json
import logging  
import inspect
from pathlib import Path
from dataclasses import dataclass, asdict, field

from typing import Any, Optional, overload, Literal
from PyQt5.QtCore import QObject
from qt_utils import TypedQtSignal

from core.json_utils import JSONWithCommentsDecoder
from core.lru_file import LeastRecentlyUsedFiles
from .language import LanguagePack

logger = logging.getLogger(__name__)
L = LanguagePack()

WORKSPACE_FILE_EXTENSION = ".translation-workspace"
DEFAULT_GLOBAL_WORKSPACE_FILE = "./default.translation-workspace"
DEFAULT_LOCAL_WORKSPACE_FILE= "./workspace.translation-workspace"
DEFAULT_SETTINGS_FILE = "settings.json"
DEFAULT_GAME_DATA_DIR = "%WORKSPACE_DIR%/data"
DEFAULT_USER_DICT_DIR = "%WORKSPACE_DIR%/dictionary"

@dataclass
class Confirmations:
    share_translation: bool = False

@dataclass
class SettingsData:
    SOURCE_LANG: str = "auto" # should be saved as language code, but can be displayed as language name in the UI
    TARGET_LANG: str = "en"   # should be saved as language code, but can be displayed as language name in the UI
    API: str = "Google"
    DEEPL_API_KEY: str = ""
    CUSTOM_API_KEY: str = ""
    CUSTOM_API_URL: str = "https://openrouter.ai/api/v1" # This is used for custom API, ignored for built-in APIs like Google Translate
    CUSTOM_API_MODEL: str = "openrouter/free"
    max_workers: int = 4
    
    # Theme and UI
    language: str = "en"
    dark_mode: bool = False
    theme: str = "default"
    
    # Recent files and session
    restore_last_session: bool = True
    recent_files: LeastRecentlyUsedFiles = field(init = False, default_factory=LeastRecentlyUsedFiles)
    last_open_workspace: Optional[str] = None  # Path to the last opened workspace, used for restoring session on startup
    
    confirmations: Confirmations = field(default_factory=Confirmations)
    
    def to_dict(self) -> dict:
        d = asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if (v is not None and not k.startswith("_"))})
        d["recent_files"] = self.recent_files.to_list()
        d["confirmations"] = asdict(self.confirmations)
        return d
    
    @classmethod
    def from_dict(cls,data: dict) -> "SettingsData":
        valid_fields = inspect.signature(cls).parameters
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        settings = cls(**filtered_data)
        settings.recent_files = LeastRecentlyUsedFiles.from_list(data.get("recent_files", []))
        settings.confirmations = Confirmations(**data.get("confirmations", {}))
        return settings
    
    @classmethod    
    def load(cls, path: str|Path) -> "SettingsData":
        try:
            with open(path, "r") as f:
                data = json.load(f, cls=JSONWithCommentsDecoder)
            settings = cls.from_dict(data)
        except FileNotFoundError:
            logger.info("Initializing new settings with default values.")
            settings=cls()  # Return default settings if file not found
        except Exception as e:
            logger.error(f"Failed to load settings from {path}: {e}")
            settings=cls()  # Return default settings on failure
        settings.DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", settings.DEEPL_API_KEY)
        settings.CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", settings.CUSTOM_API_KEY)
        # if workspace_path and Path(workspace_path).exists():
        #     settings._workspace = WorkspaceSettings.load(workspace_path)
        # else:
        #     settings._workspace = WorkspaceSettings(**data.get("workspace", {}))
        return settings
    
    def load_update(self, path: str|Path):
        """Load settings from a file and update the current settings. This is useful for loading a different settings file without affecting the workspace settings."""
        new = self.load(path)
        for k,v in new.to_dict().items():
            if v is not None:
                setattr(self, k, v)
    
    def save(self, path: str|Path="settings.json"):
        settings = self.to_dict()
        DEEPL_API_KEY =settings.pop("DEEPL_API_KEY", "")
        CUSTOM_API_KEY = settings.pop("CUSTOM_API_KEY", "")
        # if self._workspace.workspace_dir is not None:
        #     self._workspace.save(path=None)  # Save workspace settings to its own file in the workspace directory
        # else:
        #     self._workspace.save(path="./default.translation-workspace")  # Save workspace settings to a separate file with the same name but .translation-workspace extension
        if DEEPL_API_KEY or CUSTOM_API_KEY:  # Remove CUSTOM_API_KEY from the settings to be save in .env file
            import dotenv
            dotenv.set_key(".env", "DEEPL_API_KEY", DEEPL_API_KEY)
            dotenv.set_key(".env", "CUSTOM_API_KEY", CUSTOM_API_KEY)
        try:
            with open(path, "w") as f:
                json.dump(settings,  f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save settings to {path}: {e}")

@dataclass
class WorkspaceData:
    workspace_dir: Optional[str] = None  # None means the global default workspace
    game_data_dir: str = DEFAULT_GAME_DATA_DIR
    user_dict_dir: str = DEFAULT_USER_DICT_DIR
    output_dir: str = "./output"
    engine: str = "RPG Maker MV"
    db_path: str = "./user_dict.db"
    last_open_tabs: list[str] = field(default_factory=list)
    
    def asdict(self) -> dict:
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})
    
    @classmethod
    def load(cls, path: str|Path=DEFAULT_GLOBAL_WORKSPACE_FILE) -> 'WorkspaceData':
        path = Path(path)
        if path.is_dir(): # if dir given, use default workspace file name in that dir
            if (path / DEFAULT_LOCAL_WORKSPACE_FILE).exists():
                path = path / DEFAULT_LOCAL_WORKSPACE_FILE
            else: 
                logging.info(f"No workspace settings file found in {path}. Initializing with default settings.")
                return cls(workspace_dir=path.as_posix())
        if path.suffix!=".translation-workspace":
            logger.warning(f"Loading workspace settings from a file with unexpected extension: {path}. Expecting '.translation-workspace' but loading anyway.")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)
        
    def load_update(self, path: str|Path=DEFAULT_LOCAL_WORKSPACE_FILE):
        """Load workspace settings from a file and update the current settings. This is useful for loading a workspace without affecting the global settings."""
        new = self.load(path)
        for k,v in new.asdict().items():
            if v is not None:
                setattr(self, k, v)
                
    def save(self, path: Optional[str|Path] = None):
        workspace_dir = self.workspace_dir or "."
        if path is None:
            path = Path(workspace_dir) / DEFAULT_LOCAL_WORKSPACE_FILE
        else:
            path = Path(path)
        if path.suffix != ".translation-workspace":
            logger.warning(f"Saving workspace settings to a file with unexpected extension: {path}. Expecting '.translation-workspace'.")
        try: # prevent breaking the existing workspace settings if saving fails
            dumps = json.dumps(self.asdict(), indent=4, ensure_ascii=False) 
            with open(path, 'w', encoding='utf-8') as f:
                f.write(dumps)
        except Exception as e:
            logger.error(f"Error saving workspace settings to {path}: {e}")

    
    
StringSettings = Literal["SOURCE_LANG", "TARGET_LANG", "API", "DEEPL_API_KEY", "CUSTOM_API_KEY", "CUSTOM_API_URL", "CUSTOM_API_MODEL", "max_workers", "language", "theme", "last_open_workspace"]
BoolSettings = Literal["dark_mode", "restore_last_session"]
IntSettings = Literal["max_workers"]
StringWorkspaceSettings = Literal["workspace_dir", "game_data_dir", "user_dict_dir", "output_dir", "engine"]


class Settings(QObject):
    setting_changed = TypedQtSignal(str)
    workspace_changed = TypedQtSignal(str)
    data: SettingsData
    workspace_data: WorkspaceData
    # type hint for static analysis, actual attributes are stored in self.data
    SOURCE_LANG: str 
    TARGET_LANG: str
    API: str
    def __init__(self, settings: Optional[SettingsData|str|Path]=None, workspace: Optional[WorkspaceData|str|Path]=None):
        if isinstance(settings, (str, Path)):
            self.data: SettingsData = SettingsData.load(settings)
        else:
            self.data: SettingsData = settings or SettingsData()

        if isinstance(workspace, (str, Path)):
            self.workspace_data: WorkspaceData = WorkspaceData.load(workspace)
        else:
            self.workspace_data: WorkspaceData = workspace or WorkspaceData()
        super().__init__()
    # We look up the attribute string on the dataclass
    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(f"{item} not found in SettingsData or WorkspaceData.")
        
    def translate_dir(self, d:str)->str:
        d = d.replace('%WORKSPACE_DIR%', self.workspace_dir or os.getcwd())
        d = d.replace('%CWD%', os.getcwd())
        return Path(d).as_posix() # normalized dir
    @property
    def game_data_dir(self) -> str:
        return self.translate_dir(self.workspace_data.game_data_dir or DEFAULT_GAME_DATA_DIR)
    @property
    def output_dir(self) -> str:
        return self.translate_dir(self.workspace_data.output_dir)
    @property
    def user_dict_dir(self) -> str:
        return self.translate_dir(self.workspace_data.user_dict_dir or DEFAULT_USER_DICT_DIR)
    @property
    def db_path(self) -> str:
        return self.translate_dir(self.workspace_data.db_path or "./user_dict.db")
    @property
    def confirmations(self) -> Confirmations:
        return self.data.confirmations
    @overload
    def __getattr__(self, item: StringSettings|StringWorkspaceSettings) -> str: ...
    @overload
    def __getattr__(self, item: BoolSettings) -> bool: ...
    @overload
    def __getattr__(self, item: IntSettings) -> int: ...
    @overload
    def __getattr__(self, item: Literal["last_open_tabs"]) -> list: ...
    @overload
    def __getattr__(self, item: Literal["recent_files"]) -> LeastRecentlyUsedFiles: ...
    def __getattr__(self, item: str) -> Any:
        if item in ('data', 'workspace_data'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")
            
        data = self.__dict__.get('data')
        workspace_data = self.__dict__.get('workspace_data')
        
        if data and item in data.__dataclass_fields__:
            return getattr(data, item)
        elif workspace_data and item in workspace_data.__dataclass_fields__:
            return getattr(workspace_data, item)
        else:
            raise AttributeError(f"{item} not found in SettingsData or WorkspaceData.")
        
    def __setitem__(self, key: str, value: Any) -> None:
        data = self.__dict__.get('data')
        workspace_data = self.__dict__.get('workspace_data')
        
        if data:
            if hasattr(data, key):
                setattr(data, key, value)
                self.setting_changed.emit(key)  # Emit a signal when a setting is changed
                return
            elif (
                len(splits:=key.split(".")) == 2 and
                splits[0] == "confirmations" and
                hasattr(data.confirmations, splits[-1])
            ):
                setattr(data.confirmations, splits[-1], value)
                self.setting_changed.emit(key)  # Emit a signal when a setting is changed
                return
            
        if workspace_data and hasattr(workspace_data, key):
            setattr(workspace_data, key, value)
            self.workspace_changed.emit(key)  # Emit a signal when a workspace setting is changed
            return
        
        raise KeyError(f"{key} not found in wrapped data.")
        
    def __setattr__(self, key: str, value: Any) -> None:
        if key in ("data", "workspace_data") or hasattr(type(self), key):
            super().__setattr__(key, value)
        else:
            data = self.__dict__.get('data')
            workspace_data = self.__dict__.get('workspace_data')
            
            if data and hasattr(data, key):
                setattr(data, key, value)
                self.setting_changed.emit(key)  # Emit a signal when a setting is changed
            elif workspace_data and hasattr(workspace_data, key):
                setattr(workspace_data, key, value)
                self.workspace_changed.emit(key)  # Emit a signal when a workspace setting is changed
            else:
                raise AttributeError(f"{key} not found in SettingsData or WorkspaceData.")
    
    def update_workspace(self, workspace: WorkspaceData|str|Path):
        if isinstance(workspace, WorkspaceData):
            self.workspace_data = workspace
            workspace_path = workspace.workspace_dir or DEFAULT_GLOBAL_WORKSPACE_FILE
        elif isinstance(workspace, (str, Path)):
            workspace_path = Path(workspace)
            self.workspace_data.load_update(workspace_path)
        else:
            raise ValueError("Invalid workspace type. Must be WorkspaceData or path to workspace file.")
        self.add_recent_file(workspace_path)  # Add the loaded workspace to recent files
        self.workspace_changed.emit("all")  # Emit a signal indicating all workspace settings may have changed
    
    def load_last_open_workspace(self):
        last_open_workspace = self.last_open_workspace
        if last_open_workspace and Path(last_open_workspace).exists():
            logger.debug(f"Loading last open workspace from {last_open_workspace}")
            self.update_workspace(last_open_workspace)

    def load(self, path: str|Path, workspace_path: Optional[str|Path]=None):
        self.data.load_update(path)
        self.setting_changed.emit("all")  # Emit a signal indicating all settings may have changed
        if workspace_path:
            self.workspace_data.load_update(workspace_path)
            self.workspace_changed.emit("all")  # Emit a signal indicating all workspace settings may have changed
    
    def save(self, path: Optional[str|Path] = None):
        path = Path(path) if path else Path(DEFAULT_SETTINGS_FILE)
        self.data.save(path)
        self.workspace_data.save()
            
    def add_recent_file(self, file_path: str|Path):
        self.data.recent_files.add_recent_file(file_path)
        self.setting_changed.emit("recent_files")  # Emit a signal indicating recent files have changed