from deep_translator.base import BaseTranslator
from deep_translator.google import GoogleTranslator
from deep_translator.deepl import DeeplTranslator
from deep_translator.openai import OpenAITranslator

providers:dict[str, type[BaseTranslator]] = {
    "Google": GoogleTranslator,
    "DeepL": DeeplTranslator,
    "Custom API (LLM)": OpenAITranslator,
}