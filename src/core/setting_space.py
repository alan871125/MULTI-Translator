import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Any
from pydantic import BaseModel, PrivateAttr

logger = logging.getLogger(__name__)

class SettingScope(Enum):
    GLOBAL = auto()
    LOCAL  = auto()

class SettingSpace(BaseModel):
    _local: dict[str, Any] =     PrivateAttr(default_factory=dict)
    _listeners: list[Any]  =     PrivateAttr(default_factory=list)
    _parent: SettingSpace|None = PrivateAttr(default=None)
    _name: str|None =            PrivateAttr(default=None)

    if not TYPE_CHECKING:
        def __getattribute__(self, name: str) -> Any:
            if not name.startswith("_") and name in type(self).model_fields:
                try:
                    local = object.__getattribute__(self, "__pydantic_private__")["_local"]
                except (AttributeError, KeyError, TypeError):
                    local = None          # during __init__, before private attrs exist
                if local and name in local:
                    return local[name]
            return super().__getattribute__(name)
        
    def set_local(self, /, clear: bool = False, **overrides:Any, ) -> None:
        """Set a local setting value."""
        if clear:
            self._local.clear()
        for name, value in overrides.items():
            if name in type(self).model_fields:
                self._local[name] = value
            else:
                raise AttributeError(f"{name} not found in {type(self).__name__}.")
            
    def get(self, name: str, default: Any = None) -> Any:
        """Get a setting value, checking local overrides first."""
        if name in self._local:
            return self._local[name]
        return getattr(self, name, default)
    
    def get_local(self, name: str, default: Any = None) -> Any:
        """Get a local setting value, or default if not set."""
        return self._local.get(name, default)
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        elif name in self._local: 
            # let local settings intercept if defined
            self._local[name] = value
        elif name in type(self).model_fields:
            super().__setattr__(name, value)
        else:
            raise AttributeError(f"{name} not found in {type(self).__name__}.")
        
    def __setitem__(self, name: str, value: Any) -> None:
        """Allow dict-like access to settings."""
        try:
            setattr(self, name, value)
        except AttributeError:
            raise KeyError(f"{name} not found in {type(self).__name__}.")
        
    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to settings."""
        if not isinstance(key, str):
            raise TypeError(f"Key must be a string, got {type(key).__name__}.")
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(f"{key} not found in {type(self).__name__}.")
    
    def update(self, *, scope: SettingScope|None = None, **kwargs, ):
        """Update settings with new values."""
        for key, value in kwargs.items():
            if key not in type(self).model_fields:
                logger.warning(f"Attempted to update unknown setting '{key}'.")
            elif isinstance(value, dict) and isinstance(self[key], SettingSpace):
                # If the value is a dict and the field is a SettingSpace, update recursively
                self[key].update(**value, scope=scope)
            else:
                self.update_val(key, value, scope=scope)
                
    def update_val(self, name:str, value:Any, *, scope: SettingScope|None = None):
        """Update a single setting value."""
        if scope == SettingScope.GLOBAL:
            setattr(self, name, value)
        if scope == SettingScope.LOCAL or name in self._local:
            self._local[name] = value
        else:
            setattr(self, name, value)