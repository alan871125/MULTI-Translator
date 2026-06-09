import os
import json
import logging
import requests
from pathlib import Path
from core.translation.providers._base import TranslationProvider, Language, build_language_dict
from deep_translator.deepl import DeeplTranslator, Optional 

# DeepL supported languages: https://www.deepl.com/docs-api/supported-languages/
logger = logging.getLogger(__name__)

VERSION = "v3"
URL_FREE = f"https://api-free.deepl.com/{VERSION}/languages"
URL = f"https://api.deepl.com/{VERSION}/languages"
CACHE_FILE = Path(__file__).parent / "deepl_languages.json"

# Internal dynamic states
_SUPPORTED_LANGUAGES: dict[str, Language] = {}
_TARGET_ONLY_LANGUAGES: dict[str, Language] = {}
_TARGET_SUPPORTED_LANGUAGES: dict[str, Language] = {}

def is_free_api_key(api_key: str) -> bool:
    """Check if the provided API key is for the free version of DeepL."""
    return api_key.endswith(":fx")

def fetch_deepl_languages() -> list[dict]:
    """Fetch the supported languages directly from the DeepL API."""
    if not (api_key := os.getenv("DEEPL_API_KEY")):
        raise ValueError("DEEPL_API_KEY environment variable is not set.")
    
    url = URL_FREE if is_free_api_key(api_key) else URL
    headers = {"Authorization": f"DeepL-Auth-Key {api_key}"}
    params = {"resource": "translate_text"}
    
    response = requests.get(url, headers=headers, params=params)
    if not response.ok:
        logger.error("Status: %s | Response: %s", response.status_code, response.text)
    response.raise_for_status()
    return response.json()

def load_cached_languages() -> bool:
    """Load languages from local JSON cache. Returns True if successful."""
    global _SUPPORTED_LANGUAGES, _TARGET_ONLY_LANGUAGES
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _SUPPORTED_LANGUAGES = data.get("supported_languages", {})
                _TARGET_ONLY_LANGUAGES = data.get("target_only_languages", {})
                return True
        except Exception as e:
            logger.error("Failed to read language cache: %s", e)
    return False

def update_languages(force_api: bool = False) -> None:
    """
    Updates the languages mapping. 
    If force_api=True, it bypasses the cache and hits DeepL directly.
    """
    global _SUPPORTED_LANGUAGES, _TARGET_ONLY_LANGUAGES, _TARGET_SUPPORTED_LANGUAGES
    
    if not force_api and load_cached_languages():
        return  # Successfully loaded from cache

    # Fetch from API
    try:
        languages = fetch_deepl_languages()
        
        # Rebuild dictionaries safely
        new_supported = {l["lang"]: l['name'] for l in languages if l["usable_as_source"] and l["usable_as_target"]}
        new_target_only = {l["lang"]: l['name'] for l in languages if not l["usable_as_source"] and l["usable_as_target"]}
        
        _SUPPORTED_LANGUAGES = build_language_dict(new_supported)
        _TARGET_ONLY_LANGUAGES = build_language_dict(new_target_only)
        
        # Save to cache
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "supported_languages": _SUPPORTED_LANGUAGES,
                "target_only_languages": _TARGET_ONLY_LANGUAGES
            }, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        logger.error("Failed to update languages from DeepL API: %s", e)
        # Fallback to cache if API fails
        if not _SUPPORTED_LANGUAGES: 
            load_cached_languages()
    finally:
        _TARGET_SUPPORTED_LANGUAGES = {**_SUPPORTED_LANGUAGES, **_TARGET_ONLY_LANGUAGES}



# Initialize once on load (from cache or API fallback)
update_languages(force_api=False)

class classproperty:
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)

class DeeplTranslationProvider(DeeplTranslator, TranslationProvider):
    name = "DeepL"
    def __init__(self, source: str = "auto", target: str = "en", api_key: Optional[str] = os.getenv("DEEPL_API_KEY", None)):
        # Override to ensure we always use the most up-to-date language mappings
        source = self._solve_compatibility(source)
        target = self._solve_compatibility(target)
        super().__init__(source=source, target=target, api_key=api_key)

    # Use @property so these always fetch the most up-to-date data dynamically
    @classproperty
    def FULL_SUPPORTED_LANGUAGES(cls) -> dict:
        return _SUPPORTED_LANGUAGES

    @classproperty
    def SOURCE_SUPPORTED_LANGUAGES(cls) -> dict:
        return _SUPPORTED_LANGUAGES

    @classproperty
    def TARGET_SUPPORTED_LANGUAGES(cls) -> dict:
        return _TARGET_SUPPORTED_LANGUAGES
    
    def _solve_compatibility(self, code: str)->str:
        if code in self.SOURCE_SUPPORTED_LANGUAGES or code in self.TARGET_SUPPORTED_LANGUAGES:
            return code
        elif "-" in code:
            # try without region code, e.g. "en-US" -> "en"
            base_code = code.split("-")[0]
            if base_code in self.SOURCE_SUPPORTED_LANGUAGES or base_code in self.TARGET_SUPPORTED_LANGUAGES:
                logger.warning(f"Language code '{code}' is not recognized by {self.name}, but its base code '{base_code}' is supported. Using '{base_code}' for compatibility.")
                return base_code
        logger.warning(f"Language code '{code}' is not recognized by {self.name}. Please check if it's supported or if you need to update the language mappings.")
        return code  # Return original code if no compatibility mapping is found

    @classmethod
    def refresh_languages(cls) -> None:
        """Call this method anywhere in your app to force-refresh the language mappings."""
        update_languages(force_api=True)


if __name__ == "__main__":
    from core.translation.providers.google import GoogleTranslationProvider
    
    # check if all DeepL supported languages are included in the Google Translate list.
    for code, name in DeeplTranslationProvider.TARGET_SUPPORTED_LANGUAGES.items():
        if code not in GoogleTranslationProvider.FULL_SUPPORTED_LANGUAGES:
            logger.warning(f"DeepL supported language {code} ({name}) is not included in the Google Translate supported languages list.")
    print('='*100)
    for code, name in GoogleTranslationProvider.FULL_SUPPORTED_LANGUAGES.items():
        if code not in DeeplTranslationProvider.TARGET_SUPPORTED_LANGUAGES:
            logger.warning(f"Google Translate supported language {code} ({name}) is not included in the DeepL supported languages list.")