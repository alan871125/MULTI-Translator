# Features and To-Dos
This is a list of currenlty implemented and planned featuers.

## Search and replace functionality, supporting:
1. [X] Regex patterns
2. [X] Whole word match
3. [X] Case sensitivity toggle

## GUI
### Themes
1. [ ] Customable Theme Settings
2. [X] Default Themes:
   1. [X] DarkMode
   2. [X] LightMode

### Functionalities
1. [X] Translation Progress Bar
   - [X] Style 1: Circular Progress Bar
   - [ ] Style 2: Linear Progress Bar 
2. [ ] API Progress Bar (Hinting that API is processing)

### User Warnings
1. [X] Show Warning When Orignal Text is updated (Doesn't match dictionary)

## API Support
1. [X] Google Translate
   2. [X] Dynamic Language List (update deep-translator)
3. [X] DeepL
   1. [X] [deep-translator](https://github.com/nidhaloff/deep-translator) Support
   2. [X] Dynamic Language List
   3. [X] Update [deep-translator](https://github.com/nidhaloff/deep-translator) to use DeepL-v3
4. [X] Add Custom LLM API Support (Open Router by default).
   1. [X] Translation Prompt
   2. [X] Customable API URL for easier support accross different APIs (ex: Claude, OpenAI .etc)

## Project(Workspace) Management
- [X] Loading workspaces as folders or by workspace files (.translate-workspace)
- [X] Workspace-specific configurations/dictionary

## Batch Processing
1. [X] Batch search and replace with a given json/yaml file
   - [X] Support regex search and replacements
   - [ ] Add Translation Placeholders with different signs to translated specific parts of the text:
       - $: No Translation (Same as Regex)
       - #: Translator
       - %: Dictionary
       - Note: Might want to use other signs for easier implementations, and prevent hard to fix conflicts with regex.
2. [X] Chinese Simplified <-> Chinese Traditional Convertions
3. [ ] Batch-batch processing: Batch process batch processing functionalities on multiple files once

## Translation Level and Highlighting
- [X] Multi level translation for quality and progress tracking (Inspired by xTranslate). 
  1. [X] Untranslated
  2. [X] Heuristic Translation
     - Currently implemented by fuzzing matching the dictionary database.
  3. [X] Partially Translated (currently: Manully Marked only)
  4. [X] API Translation
  5. [X] Dictionary (imported From (other) Dictionary)
  6. [X] Verified Translation (currently: whenever Edit is Done)
- [X] Add background color (text color in dark mode) for each level.

## History Tracing
1. [X] Keep a queue of Actions to Redo/Undo when regret.
2. [X] Trace a List of Recent Files
3. [X] Allow keeping a dictionary(*.json ?) of saved translations for each game file. Should be key:translation pairs. (Optional) With some other meta data included.
   - [X] save
   - [X] load

## Hot Key Supports
-  [ ] User Customable Hot Key Settings
1. [X] CTRL+S: Save Dictionary
2. [X] CTRL+C: Copy Translation/Original
3. [X] CTRL+V: Paste Translation
4. [X] CTRL+Z: Undo Action
5. [X] CTRL+Y: Redo Action
6. [ ] CTRL+T: API Translation (Popup for Confirmation before action, with a check box to allow user to skip the confirmation. Add in settings incase users regret.)
7. [X] CTRL+F: Popup Search Window
8. [X] CTRL+J: Trigger Bottom Panel
9. [X] CTRL+`: Trigger Console Window
10. [X] F1~F?: Mark translation Level (similar to xTranslate)
11. [X] CTRL+F1~F?: Toggle level filter
12. [X] CTRL+SHIFT+F1~F?: Toggle level filter (exclusive, only show the selected level)

## Supported Engines:
- [X] RPG Maker MV/MZ
- [X] Rimworld
- [X] Paradox Games: Crusader Kings 3