
import os
import opencc
import logging
from typing import Protocol, Iterable, Sequence, Optional

from core.translation._language import Language

from ._providers import providers

logger = logging.getLogger(__name__)

class TranslatorProtocol(Protocol):
    _languages: dict[str, Language]
    def translate(self, text: str, **kwargs) -> str:
        ...
    def _translate_batch(self, batch: list[str], **kwargs) -> Sequence[str|None]:
        ...
    
class TranslatorSettings(Protocol):
    SOURCE_LANG: str
    TARGET_LANG: str
    API: str

class Translator:
    """A wrapper class to unify the interface of different translation providers.
    And also links the translation settings from the app's Settings for easier use in the GUI and other parts of the app.
    """
    def __init__(self, settings: TranslatorSettings):
        """
        Arguments:
            settings (TranslatorSettings): 
                Required attributes:
                * SOURCE_LANG (str)
                * TARGET_LANG (str)
                * API (str)
        """
        
        self.settings = settings
    def translate(self, text: str):
        return translate(
            text,
            source_lang=self.settings.SOURCE_LANG,
            target_lang=self.settings.TARGET_LANG,
            provider=self.settings.API,
        )
    def batch_translate(self, batch: list[str]) -> Sequence[str|None]:
        return batch_translate(
            batch,
            source_lang=self.settings.SOURCE_LANG,
            target_lang=self.settings.TARGET_LANG,
            provider=self.settings.API,
        )
    def get_supported_languages(self) -> list[Language]:
        return get_supported_languages(self.settings.API)
        
def get_supported_languages(api:str, role:Optional[str] = None) -> list[Language]:
    """
    Get the list of supported languages from the translation provider based on the current settings.

    Arguments:
        api (str): The translation provider to use.
        role (Optional[str]): `"source"` or `"target"`. Use `None` for both.
    """
    if (translator := get_translator('auto', 'en', provider=api)) is None:
        return []
    elif role is None:
        return list(translator._languages.values())
    elif role == "source":
        return list(lang for lang in translator._languages.values() if lang.is_source)
    elif role == "target":
        return list(lang for lang in translator._languages.values() if lang.is_target)
    return []
    

def get_translator(source_lang: str, target_lang: str, provider: str, api_key: str|None = None) -> TranslatorProtocol|None:
    """Helper function to get translation settings, 
    including mapping language names to codes based on the provider's supported languages."""
    # Map language names to codes based on the provider's supported languages
    # Safe if the input is already a code.
    if provider in providers:
        if provider == 'DeepL' and not api_key:
            api_key = os.getenv("DEEPL_API_KEY")
        elif provider == 'Custom API (LLM)' and not api_key: 
            api_key = os.getenv("CUSTOM_API_KEY")
    else:
        logger.error(f"Unsupported translation provider: {provider}")
        return None
    if (translator_class := providers.get(provider)) is None:
        logger.error(f"Unsupported translation provider: {provider}")
        return None
    translator = translator_class(
        source=source_lang, target=target_lang, api_key=api_key
    )
    return translator

def translate(source:str, source_lang:str="auto", target_lang:str="en", provider:str = 'google', api_key:str|None=None)-> str|None:
    """Translate the source text from source_lang to target_lang using the specified provider and API key.
    
    Arguments:
        source (str): the text to be translated
        source_lang (str): the language code of the source text, default is "auto" for auto-detection
        target_lang (str): the language code to translate to, default is "en" for English
        provider (str): the translation provider to use, either 'google' or 'deepl', default is 'google'
        api_key (str): the API key for the translation provider, required for some providers like Deepl
    """
    if not source or not source.strip():
        return None
    try:
        translator = get_translator(source_lang, target_lang, provider, api_key)
        if not translator:
            return None
        translated = translator.translate(source)
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return None
    return translated

def batch_translate(sources: list[str], source_lang:str="auto", target_lang:str="en", provider:str = 'google', api_key:str|None=None) -> Sequence[str|None]:
    """Batch translate a sequence of source texts from source_lang to target_lang using the specified provider and API key.
    """
    if not sources:
        return []
    try:
        translator = get_translator(source_lang, target_lang, provider, api_key)
        if not translator:
            return []
        translated = translator._translate_batch(sources)
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return []
    return translated

def batch_chinese_convertion(texts: Iterable[str], target:str='tw')-> Sequence[str]:
    """Batch convert a sequence of Chinese texts between Simplified and Traditional variants using OpenCC.  
    
    (Loads the OpenCC converter once and applies it to all texts for better performance compared to calling chinese_convertion multiple times.)
    Arguments:
        texts (Sequence[str]): the sequence of texts to be converted
        target (str): the target Chinese variant, either 's' for Simplified or 'tw' for Traditional. Default is 'tw'.    
    """
    if target.lower() in ['s','simplified', 'chs','cn','zh-cn', 'zh-hans']:
        convertion_file = 'tw2s.json'
    elif target.lower() in ['t','traditional', 'cht','tw','zh-tw', 'zh-hk', 'zh-hant']:
        convertion_file = 's2tw.json'
    else:
        logger.error(f"Unsupported Chinese conversion target: {target}. Use either 's' or 'tw'.")
        # Return the original texts if conversion is not supported
        return list(texts)
    converter = opencc.OpenCC(convertion_file)
    return [converter.convert(text) for text in texts]

def chinese_convertion(text:str, target:str='tw')-> str:
    """Convert Chinese text between Simplified and Traditional variants using OpenCC.<br>  
    
    ***Note:** This is a wrapper around `batch_chinese_convertion` for single strings for convenience.
    Use `batch_chinese_convertion` directly for better performance when converting multiple strings to avoid the overhead of loading the OpenCC converter multiple times.*
    
    Arguments:
        text (str | Sequence[str]): the text or sequence of texts to be converted
        target (str): the target Chinese variant, either 's' for Simplified or 'tw' for Traditional. Default is 'tw'.    
    """
    return batch_chinese_convertion([text], target=target)[0]
