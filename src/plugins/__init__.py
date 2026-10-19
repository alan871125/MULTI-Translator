import sys 
import pkgutil
import importlib
import logging
from pathlib import Path
from ._registry import extractors, engine_modules
from ._base import BaseExtractor

logger = logging.getLogger(__name__)

# Two ways to register a plugin:
# 1. use the @registered_extractor decorator in the engine's extractor module: see simple_json.py for an example
# 2. define the name variable and Extractor class in the engine submodule: see rimworld/__init__.py for an example

# 1. Determine external plugins directory (beside .exe when frozen, or repo root in dev)
if getattr(sys, "frozen", False):
    external_plugins_dir = Path(sys.executable).parent / "plugins"
else:
    external_plugins_dir = Path(__file__).resolve().parents[2] / "plugins"

# 2. Add external directory to package search path
if external_plugins_dir.is_dir() and str(external_plugins_dir) not in __path__:
    __path__.append(str(external_plugins_dir))

# 3. pkgutil now automatically searches BOTH internal and external directories!
for finder, modname, ispkg in pkgutil.iter_modules(__path__):
    try:
        mod = importlib.import_module(f"{__name__}.{modname}")
        # prefer module-provided engine_name, otherwise use package name
        engine_name = getattr(mod, "name", modname)
        if engine_name.startswith("_"):  # Skip private modules
            continue  # Skip the base module as it's not an actual engine
        engine_modules[engine_name] = mod
        # Check if the module has an extractor class
        if hasattr(mod, "Extractor"):
            extractors[engine_name] = mod.Extractor
    except Exception as e:
        logger.exception("Failed importing engine module %s with error: %s", modname, e)

plugin_list = list(extractors.keys())
