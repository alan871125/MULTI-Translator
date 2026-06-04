# src/engines/__init__.py
import pkgutil
import importlib
import logging

logger = logging.getLogger(__name__)

supported_engines = []              # list of engine names (strings)
engine_modules: dict = {}           # engine_name -> module object
extractors:dict[str, type] = {}  # engine_name -> Extractor class
for finder, modname, ispkg in pkgutil.iter_modules(__path__):
    try:
        mod = importlib.import_module(f"{__name__}.{modname}")
        # prefer module-provided engine_name, otherwise use package name
        engine_name = getattr(mod, "name", modname)
        supported_engines.append(engine_name)
        engine_modules[engine_name] = mod
        # Check if the module has an extractor class
        if hasattr(mod, "Extractor"):
            extractors[engine_name] = mod.Extractor
    except Exception as e:
        logger.exception("Failed importing engine module %s with error: %s", modname, e)