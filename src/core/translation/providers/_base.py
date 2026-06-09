from abc import ABC, abstractmethod
from typing import Optional

            
class Language(str):
    """A helper class to represent a language in the UI, 
    allowing for more user-friendly display of language names while still keeping track of the underlying language code
    """
    code: str
    def __new__(cls, code:str, name:str):
        instance = super().__new__(cls, name)
        instance.code = code
        return instance
    
def build_language_dict(lang_dict: dict[str, str]) -> dict[str, Language]:
    """Helper function to build a dictionary of language code to Language objects from a dictionary of language code to language name"""
    return {code: Language(code, name) for code, name in lang_dict.items()}

class TranslationProvider(ABC):
    FULL_SUPPORTED_LANGUAGES: dict[str, Language]
    TARGET_SUPPORTED_LANGUAGES: dict[str, Language]
    SOURCE_SUPPORTED_LANGUAGES: dict[str, Language]
    
    @abstractmethod
    def __init__(self, source: str, target: str, api_key: Optional[str] = None):
        """Initialize the translation provider with the specified source and target languages, and an optional API key if required by the provider."""
        ...
    def is_language_supported(self, source_lang: Optional[str]=None, target_lang: Optional[str]=None) -> bool:
        """Check if the specified languages are supported by the translation provider.

        Arguments:
            source_lang (str): the source language code to check
            target_lang (str): the target language code to check
        """
        if source_lang is None and target_lang is None:
            raise ValueError("At least one of 'source_lang' or 'target_lang' must be provided.")
        if source_lang is not None:
            if source_lang not in self.SOURCE_SUPPORTED_LANGUAGES:
                return False
        if target_lang is not None:
            if target_lang not in self.TARGET_SUPPORTED_LANGUAGES:
                return False
        return True
    
    @abstractmethod
    def translate(self, text: str) -> str:
        ...
        
    def translate_batch(self, texts: list[str]) -> list[str]:
        """A helper method to translate a batch of texts more efficiently than calling `translate` multiple times. Not all providers may implement this method, in which case the default implementation will call `translate` for each text."""
        return [self.translate(text) for text in texts]