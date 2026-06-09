from ._base import TranslationProvider
from .deepl import DeeplTranslationProvider
from .google import GoogleTranslationProvider

providers:dict[str, type[TranslationProvider]] = {
    "DeepL": DeeplTranslationProvider,
    "Google": GoogleTranslationProvider,
}