import json
import logging
from pathlib import Path
from PySide6.QtCore import QTranslator
logger = logging.getLogger(__name__)

_TRANSLATIONS_DIR = Path(__file__).parent.resolve()
class LanguagePack:
    """
    Use with
    ```
    import LanguagePack
    L = LanguagePack()
    print(L["hello"])
    ```
    """
    
    qt_translator = QTranslator()
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
        
        langs = cls.LANGUAGE if cls.LANGUAGE == "en" else f"{cls.LANGUAGE} or en"
        logger.warning(f"Untranslated key '{key}' in language {langs}. Returning key as fallback.")
        return key

    @classmethod
    def load_translations(cls, lang, force=False):
        if not force and lang in cls.lang_data:
            return
        if not _TRANSLATIONS_DIR.exists():
            logger.error(f"Translations directory '{_TRANSLATIONS_DIR}' does not exist. No translations loaded.")
            cls.lang_data[lang] = {}
            return
        with open(_TRANSLATIONS_DIR / f"{lang}.json", "r", encoding="utf-8") as f:
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
        cls.set_qt_translator(lang)
        
    @classmethod    
    def set_qt_translator(cls, lang):
        from PySide6.QtCore import QLibraryInfo, QCoreApplication
        app = QCoreApplication.instance()

        # Get the path to Qt's built-in translation files
        translations_path = QLibraryInfo.path(
            QLibraryInfo.LibraryPath.TranslationsPath
        )
        lang = lang.replace("-", "_")  # Qt uses underscores in language codes
        if app and cls.qt_translator.load(f"qtbase_{lang}", translations_path):
            app.installTranslator(cls.qt_translator)
                    
LanguagePack.load_translations(LanguagePack.LANGUAGE)


    