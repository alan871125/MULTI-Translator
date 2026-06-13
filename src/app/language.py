import json
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

_TRANSLATIONS_DIR = Path(__file__).parent / ".translations"
class LanguagePack:
    """
    Use with
    ```
    import LanguagePack
    L = LanguagePack()
    print(L["hello"])
    ```
    """
    
    lang_data = {}
    LANGUAGE = "en"
    def __init__(self, LANGUAGE=None):
        if LANGUAGE is not None:
            self.set_language(LANGUAGE)
    @staticmethod
    def get_available_languages():
        return [p.stem for p in _TRANSLATIONS_DIR.glob("*.json")]
    
    @classmethod
    def __getitem__(cls, key)->str:
        # fallback order: current language -> English -> key itself
        if (found := cls.lang_data[cls.LANGUAGE].get(key)) is not None:
            return found
        elif (found := cls.lang_data.get("en", {}).get(key)) is not None:
            logger.warning(f"Untranslated key '{key}' in language '{cls.LANGUAGE}'. Falling back to English.")
            return found
        # elif (key_last_part := key.split(".")[-1])!=key:
        #     return cls.__getitem__(key_last_part)  # try fallback to last part of the key, e.g. "settings.startup" -> "startup"
        logger.warning(f"Untranslated key '{key}' in language '{cls.LANGUAGE}' and English. Returning key as fallback.")
        return key

    @classmethod
    def load_translations(cls, lang, force=False):
        if not force and lang in cls.lang_data:
            return
        with open(Path(__file__).parent/f".translations/{lang}.json", "r", encoding="utf-8") as f:
            cls.lang_data[lang] = json.load(f)
    
    @classmethod
    def set_language(cls, lang):
        cls.LANGUAGE = lang
        try:
            cls.load_translations(lang)
        except FileNotFoundError:
            logger.warning(f"Translation file for language '{lang}' not found. Falling back to English.")
            cls.LANGUAGE = "en"
            cls.load_translations("en")
            
LanguagePack.load_translations(LanguagePack.LANGUAGE)


    