#  M.U.L.T.I: Modular Universal Localization & Translation Interface
[![Python](https://img.shields.io/badge/Python-3.13.12-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.7.1-blue.svg)](https://pypi.org/project/PySide6/)

This is a universal translation editor designed provide a extensible and modular translation interface for various game engines and file formats.
Helping game or mod translators to use a single interface to easily mangage, restore and apply translation from all sources.


*This project is higly inspired by [xTranslator](https://github.com/MGuffin/xTranslator), a great tool designed for Bethesda games.*
## Support List:
  - RPG Maker MV/MZ
  - RimWorld
  - Paradox Games (Crusader Kings III)
  - Simple JSON (extracts any strings found)
  - *Add more custom file support by defining your own translaiton extractors*

## Main Features
- **Translation Editing**
  - Common editing hot key supports: copy/paste/undo/redo
  - Highlted texts for different translation levels
- **Translation Workspace (Session)**:
  - Manage your translations as workspaces
  - Save and restore your translation progress.
- **Translation Dictionary**:
  - Save translations as dictionaries
  - Easily update files by importing existing dictionaries
- **Translation Tools and APIs**:
  - Translation API Supports:
    - Google Translation(Free)
    - DeepL (API key required)
    - Any Custom LLM API (API Key required)
  - Chinese Converstions (CHT<->CHS)
- **Batch Processing**
  - Batch Regex Replacements

### Planning Features
- UI Enhancements
- Engine(Game) Support Expansion

See the [To-do list](./TODO.MD) for more details.


## How to Start (Dev)
### Requirements
```bash
pip install -r requirements.txt
```
For a full development environment use this instead:
```bash
pip install -r requirements-dev.txt
```

### Compile Qt Resources
```bash
pyside6-rcc resources.qrc -o src/app/resources_rc.py
```
or 
```python
python build.py
```
### Start the Translator App
```python
python src/main.py
```

Common translation API endpoints:
- Google AI Studio: https://generativelanguage.googleapis.com/v1beta/openai/ ([Get Free API key](https://aistudio.google.com/api-keys))
- OpenAI: https://api.openai.com/v1/chat/completions
- OpenRouter: https://api.openrouter.ai/v1/chat/completions