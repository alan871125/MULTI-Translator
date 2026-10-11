import logging
from types import ModuleType
from typing import Optional, overload, Callable, TypeVar
from ._base import BaseExtractor

logger = logging.getLogger(__name__)

extractors: dict[str, type[BaseExtractor]] = {}  # engine_name -> Extractor class/factory
engine_modules: dict[str, ModuleType] = {}           # engine_name -> module object

T = TypeVar("T", bound="BaseExtractor")
@overload
def registered_extractor(
    _cls: None = None,
    *,
    name: Optional[str] = None,
) -> Callable[[type[T]], type[T]]: ...

@overload
def registered_extractor(
    _cls: type[T],
    *,
    name: Optional[str] = None,
) -> type[T]: ...

def registered_extractor(
    _cls: Optional[type[T]] = None,
    *,
    name: Optional[str] = None,
) -> type[T] | Callable[[type[T]], type[T]]:
    """Decorator to register an extractor class with the engine.
    
    Example:
    ```
    # This register the SimpleJsonExtractor class with the engine name 'Simple JSON'
    @registered_extractor(name='Simple JSON')
    class SimpleJsonExtractor(BaseExtractor):
        ...
    ```
    """
    def decorator(cls: type[T]) -> type[T]:
        engine_name = name or getattr(cls, "NAME", cls.__name__)
        extractors[engine_name] = cls
        return cls

    if _cls is not None:
        return decorator(_cls)
    return decorator

