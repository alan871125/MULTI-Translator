# TODO List
This is a list of To-Dos, where the ones on the top are with higher priority.
Some of the functionalities may be higly related, the order is therefore not necessarily fixed.

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
3. [ ] Translation Progress Bar
4. [ ] API Progress Bar (Hinting that API is processing)
5. [ ] (Low priority) Add translation Author tracing (Manual/Google/DeepL/LLM)
### User Warnings
1. [ ] Show Warning When Orignal Text is updated (Doesn't match dictionary)

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
1. [ ] Batch search and replace with a given json File, or csv (cleaner for more different patterns).
   - Support regex search and replacements
   - Some Random Example of a pattern
        - **Note*: mode
        ```{json}
            {
                "PATTERN": "([^\s])BUFF",
                "REPLACE": "\[$1\] BUFF",
                "REGEX": 1,
                "CASE_SENSITIVE":1
                "WHOLE_MATCH":1
            }
        ```
   - Use different Signs to represent different Translation Methods. Example:
       - $: No Translation (Same as Regex)
       - #: Translator
       - %: Dictionary
       - Note: Might want to use other signs for easier implementations, and prevent hard to fix conflicts with regex.
2. [X] Chinese Simplified <-> Chinese Traditional Convertions
3. [ ] Batch-batch processing: Batch process batch processing functionalities on multiple files once

## Translation Level and Highlighting
- [ ] Multi level translation for quality and progress tracking (Inspired by xTranslate). 
  1. [X] Untranslated
  2. [X] API Translation
  3. [ ] Partially Translated (currently: Manully Marked only)
  4. [X] Verified Translation (currently: whenever Edit is Done)
  5. [ ] Translated (From (other) Dictionary)
  6. [ ] Batch Processed
  7. [ ] Heuristic Translation
     (A functionality in xTranslator Not Sure what it actually is)
     - Suppose using word2vec or fuzzy matching to find similar text
- [x] Add background color for each level.

## History Tracing
1. [X] Keep a queue of Actions to Redo/Undo when regret.
2. [X] Trace a List of Recent Files
3. [X] Allow keeping a dictionary(*.json ?) of saved translations for each game file. Should be key:translation pairs. (Optional) With some other meta data included.
   - [X] save
   - [X] load

## Hot Key Supports
1. [X] CTRL+S: Save Dictionary
2. [X] CTRL+C: Copy Translation/Original
3. [X] CTRL+V: Paste Translation
4. [X] CTRL+Z: Undo Action
5. [X] CTRL+Y: Redo Action
6. [ ] CTRL+T: API Translation (Popup for Confirmation before action, with a check box to allow user to skip the confirmation. Add in settings incase users regret.)
7. [X] CTRL+F: Popup Search Window
8. [X] F1~F?: Mark translation Level (similar to xTranslate)

## Supported Engines:
- [X] RPG Maker MV
  - [X] Extract and Apply
- [X] Rimworld
  - [X] Extract and Apply
  - [ ] Supported Language check
### Planning:
- [ ] Paradox Games: Crusader Kings 3