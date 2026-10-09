# GG-Translator: Generic Game Translator
This is a translation editor designed to help game or mod translators to easily mangage, restore and apply translations. 

*This project is higly inspired by xTranslate (designed for Bethesda games).*


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
- **Game Engine Support**:
  - RPG Maker MV/MZ
  - RimWorld
  - Paradox Games (Crusader Kings III)
  - Simple JSON (extracts any strings found)
  - *Add more custom file support by defining your own translaiton extractors*
- **Batch Processing**
  - Batch Regex Replacements
### Planning Features
- UI Enhancements
- Engine(Game) Support Expansion
- Heuristic Translation

See the [To-do list](./TODO.MD) for more details.


## How to Start (Dev)
### Requirements
```bash
pip install -r requirements-dev.txt
```
### Compile Qt Resources
```bash
pyrcc5 src/app/resources.qrc -o src/app/resources_rc.py
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