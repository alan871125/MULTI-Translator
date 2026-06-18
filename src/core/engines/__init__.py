# src/engines/__init__.py
import pkgutil
import importlib
import logging
from collections.abc import Callable
from types import ModuleType
from ._base import BaseExtractor

logger = logging.getLogger(__name__)

supported_engines = []              # list of engine names (strings)
engine_modules: dict[str, ModuleType] = {}           # engine_name -> module object
extractors: dict[str, type[BaseExtractor]] = {}  # engine_name -> Extractor class/factory
for finder, modname, ispkg in pkgutil.iter_modules(__path__):
    try:
        mod = importlib.import_module(f"{__name__}.{modname}")
        # prefer module-provided engine_name, otherwise use package name
        engine_name = getattr(mod, "name", modname)
        if engine_name == "_base":
            continue  # Skip the base module as it's not an actual engine
        supported_engines.append(engine_name)
        engine_modules[engine_name] = mod
        # Check if the module has an extractor class
        if hasattr(mod, "Extractor"):
            extractors[engine_name] = mod.Extractor
    except Exception as e:
        logger.exception("Failed importing engine module %s with error: %s", modname, e)