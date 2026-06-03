import json
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

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
        
    @classmethod
    def __getitem__(cls, key)->str:
        # fallback order: current language -> English -> key itself
        return cls.lang_data[cls.LANGUAGE].get(key, None) or cls.lang_data.get("en", {}).get(key, key)

    @classmethod
    def load_translations(cls, lang):
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


    