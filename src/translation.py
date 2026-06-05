
import logging
import os
from typing import Iterable, Sequence
import opencc
from deep_translator import GoogleTranslator, DeeplTranslator
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES, DEEPL_LANGUAGE_TO_CODE


from app.settings import Settings

logger = logging.getLogger(__name__)


providers = {
    'google': GoogleTranslator,
    'deepl': DeeplTranslator
}

class Translator:
    """A wrapper class to unify the interface of different translation providers.
    And also links the translation settings from the app's Settings for easier use in the GUI and other parts of the app.
    """
    settings: Settings
    def __init__(self, settings: Settings):
        self.settings = settings
    def translate(self, source: str):
        return translate(
            source,
            source_lang=self.settings.SOURCE_LANG,
            target_lang=self.settings.TARGET_LANG,
            provider=self.settings.API
        )

def translate(source:str, source_lang:str="auto", target_lang:str="en", provider:str = 'google', api_key:str|None=None)-> str|None:
    """Translate the source text from source_lang to target_lang using the specified provider and API key.
    
    Arguments:
        source (str): the text to be translated
        source_lang (str): the language code of the source text, default is "auto" for auto-detection
        target_lang (str): the language code to translate to, default is "en" for English
        provider (str): the translation provider to use, either 'google' or 'deepl', default is 'google'
        api_key (str): the API key for the translation provider, required for some providers like Deepl
    """
    if provider.lower() == 'deepl' and not api_key:
        api_key = os.getenv("DEEPL_API_KEY")
    if not source or not source.strip():
        return None
    # Call translation API (e.g. Google Translate) and update translation
    if (translator_class := providers.get(provider.lower())) is None:
        logger.error(f"Unsupported translation provider: {provider}")
        return None
    translator = translator_class(
        source_lang, target_lang, api_key=api_key
    )
    try:
        translated = translator.translate(source)
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return None
    return translated

def batch_chinese_convertion(texts: Iterable[str], target:str='tw')-> Sequence[str]:
    """Batch convert a sequence of Chinese texts between Simplified and Traditional variants using OpenCC.  
    
    (Loads the OpenCC converter once and applies it to all texts for better performance compared to calling chinese_convertion multiple times.)
    Arguments:
        texts (Sequence[str]): the sequence of texts to be converted
        target (str): the target Chinese variant, either 's' for Simplified or 'tw' for Traditional. Default is 'tw'.    
    """
    if target.lower() in ['s','simplified', 'chs','cn','zh-cn']:
        convertion_file = 'tw2s.json'
    elif target.lower() in ['t','traditional', 'cht','tw','zh-tw']:
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
