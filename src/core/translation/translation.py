
import os
import json
import opencc
import logging
from typing import Literal, Protocol, Iterable, Sequence, Optional, Iterable

from deep_translator.base import Language
from deep_translator.openai import OpenAITranslator
from ._providers import providers

logger = logging.getLogger(__name__)

class TranslatorProtocol(Protocol):
    @property
    def supported_languages(self) -> Iterable[Language]:
        ...
    @property
    def source_supported_languages(self) -> Iterable[Language]:
        ...
    @property
    def target_supported_languages(self) -> Iterable[Language]:
        ...
    def translate(self, text: str, **kwargs) -> str:
        ...
    def _translate_batch(self, batch: list[str], **kwargs) -> Sequence[str|None]:
        ...
    
class TranslatorSettings(Protocol):
    source_lang: str
    target_lang: str
    api_provider: str
    custom_api_model:str
    custom_api_url:str

class Translator:
    """A wrapper class to unify the interface of different translation providers.
    And also links the translation settings from the app's Settings for easier use in the GUI and other parts of the app.
    """
    def __init__(self, settings: TranslatorSettings):
        """
        Arguments:
            settings (TranslatorSettings): 
                Required attributes:
                * source_lang (str)
                * target_lang (str)
                * api_provider (str)
                * custom_api_model (str)
                * custom_api_url (str)
        """
        
        self.settings = settings
    def translate(self, text: str):
        return translate(
            text,
            source_lang=self.settings.source_lang,
            target_lang=self.settings.target_lang,
            provider=self.settings.api_provider,
            model=self.settings.custom_api_model,
            base_url=self.settings.custom_api_url
        )
    def batch_translate(self, batch: list[str]) -> Sequence[str|None]:
        return batch_translate(
            batch,
            source_lang=self.settings.source_lang,
            target_lang=self.settings.target_lang,
            provider=self.settings.api_provider,
            model=self.settings.custom_api_model,
            base_url=self.settings.custom_api_url
        )
    def get_supported_languages(self) -> list[Language]:
        return list(get_supported_languages(self.settings.api_provider))
    
    def line_batch_translate(self, lines:list[str]):
        """(EXPERIMENTAL) Translate a sequence of lines as a whole, yet preserving formatting, decided by the llm model"""
        # TODO: THIS IS EXPERIMENTAL
        system_prompt = (
            "You are a professional translator specializing in {engine_name} games."
            "You will be provided several lines of text in JSON format." 
            "Please translate the text from the lines as a whole in to {target_lang}."
            "Preserve any {engine_name} specifi formatting, special characters, and placeholders in the original text."
            "Output the translated text in PURE JSON format with no markdown, maintaining the same structure as the input."
        )
        
        translation_prompt =  "Source JSON:\n{text}\nTranslated JSON:\n"
        if self.settings.api_provider!= "Custom API (LLM)":
            logger.error(f"line_batch_translate is designed for Custom API (LLM) provider. Current provider is {self.settings.api_provider}.")
            return None
        
        # translator = get_translator(source_lang, target_lang, self.settings.API, api_key=os.getenv("CUSTOM_API_KEY"), model=self.settings.CUSTOM_API_MODEL, base_url=self.settings.CUSTOM_API_URL)
        translator = OpenAITranslator(
            model=self.settings.custom_api_model, 
            api_key=os.getenv("CUSTOM_API_KEY"), 
            base_url=self.settings.custom_api_url,
            source=self.settings.source_lang, target=self.settings.target_lang
        )
        if not translator:
            logger.error(f"Failed to get translator for provider {self.settings.api_provider}.")
            return None
        try:
            translated_json = translator.translate(json.dumps(lines, ensure_ascii=False, indent=2), system_prompt=system_prompt, main_prompt=translation_prompt)
            if translated_json is None:
                return None
            try:
                return json.loads(translated_json)
            except Exception as e:
                logger.error(f"Error parsing translated JSON: {e}")
                return [translated_json] * len(lines) # Return the raw translated text in a list if JSON parsing fails
        except Exception as e:
            logger.error(f"Error during line_batch_translate: {e}")
            return None
        
def get_supported_languages(api:str, role:Optional[Literal["source", "target"]] = None) -> Iterable[Language]:
    """
    Get the list of supported languages from the translation provider based on the current settings.

    Arguments:
        api (str): The translation provider to use.
        role (Optional[str]): `"source"` or `"target"`. Use `None` for both.
    """
    if (translator := get_translator('auto', 'en', provider=api)) is None:
        return []
    elif role is None:
        return translator.supported_languages
    elif role == "source":
        return translator.source_supported_languages
    elif role == "target":
        return translator.target_supported_languages
    return []
    

def get_translator(source_lang: str, target_lang: str, provider: str, api_key: str|None = None, **kwargs) -> TranslatorProtocol|None:
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
            kwargs.pop("base_url", None)  # Remove base_url from kwargs to avoid passing it twice
    else:
        logger.error(f"Unsupported translation provider: {provider}")
        return None
    if (translator_class := providers.get(provider)) is None:
        logger.error(f"Unsupported translation provider: {provider}")
        return None
    translator = translator_class(
        source=source_lang, target=target_lang, api_key=api_key, **kwargs
    )
    return translator

def translate(source:str, source_lang:str="auto", target_lang:str="en", provider:str = 'google', api_key:str|None=None, **kwargs)-> str|None:
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
        translator = get_translator(source_lang, target_lang, provider, api_key, **kwargs)
        if not translator:
            return None
        translated = translator.translate(source)
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return None
    return translated

def batch_translate(sources: list[str], source_lang:str="auto", target_lang:str="en", provider:str = 'google', api_key:str|None=None, **kwargs) -> Sequence[str|None]:
    """Batch translate a sequence of source texts from source_lang to target_lang using the specified provider and API key.
    """
    if not sources:
        return []
    try:
        translator = get_translator(source_lang, target_lang, provider, api_key, **kwargs)
        if not translator:
            return []
        translated = translator._translate_batch(sources)
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return []
    return translated
ChineseType = Literal['s', 't', 'tw', 'zh-cn', 'zh-tw', 'zh-hans', 'zh-hant', 'simplified', 'traditional', 'chs', 'cht']
def batch_chinese_convertion(texts: Iterable[str], target:ChineseType='tw')-> Sequence[str]:
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

def chinese_convertion(text:str, target:ChineseType='tw')-> str:
    """Convert Chinese text between Simplified and Traditional variants using OpenCC.<br>  
    
    ***Note:** This is a wrapper around `batch_chinese_convertion` for single strings for convenience.
    Use `batch_chinese_convertion` directly for better performance when converting multiple strings to avoid the overhead of loading the OpenCC converter multiple times.*
    
    Arguments:
        text (str | Sequence[str]): the text or sequence of texts to be converted
        target (str): the target Chinese variant, either 's' for Simplified or 'tw' for Traditional. Default is 'tw'.    
    """
    return batch_chinese_convertion([text], target=target)[0]
