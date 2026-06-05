# TODO List
This is a list of To-Dos, where the ones on the top are with higher priority.
Some of the functionalities may be higly related, the order is therefore not necessarily fixed.


## Search and replace functionality, supporting:
1. [X] Regex patterns
2. [X] Whole word match
3. [X] case sensitivity toggle

## UI Functionalities and Themes
1. [ ] Customable Theme Settings
2. [X] Default Themes:
   1. [X] DarkMode
   2. [X] LightMode

## API Support
1. [X] Google Translate
2. [X] DEEPL
3. [ ] Add Custom LLM API Support (Open Router).
   1. Write a Translation Prompt
   2. Should use API URL for easier support accross different APIs (ex: Claude, OpenAI .etc)

## Batch Processing
1. [ ] Batch search and replace with a given json File, or csv (cleaner for more different patterns).
   - Support regex search and replacements
   - Some Random Example of a pattern
        - **Note*: mode
        ````{json}
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
   - 
2. [X] Chinese Simplified <-> Chinese Traditional Convertions

## Translation Level and Highlighting
- [ ] Multi level translation for quality and progress tracking (Inspired by xTranslate). 
  1. Untranslated
  2. API Translation
  3. Partially Translated
  4. Verified Translation
  5. Translated (From Dictionary)
  6. Batch Processed (Should be Highlighted differently)
  7. Heuristic Translation ?????????
     (A functionality in xTranslator Not Sure what it actually is)
- [x] Add background color for each level.

## History Tracing
1. [ ] Keep a queue of Actions to Redo/Undo when regret.
2. [ ] Trace a List of Recent Files
3. [ ] Allow keeping a dictionary(*.json ?) of saved translations for each game file. Should be key:translation pairs. (Optional) With some other meta data included.

## Hot Key Supports
1. [ ] CTRL+S: Save Dictionary
2. [ ] CTRL+C: Copy Translation
3. [ ] CTRL+V: Paste Translation
4. [ ] CTRL+Z: Undo Action
5. [ ] CTRL+Y: Redo Action
6. [ ] CTRL+T: API Translation (Popup for Confirmation before action, with a check box to allow user to skip the confirmation. Add in settings incase users regret.)
7. [X] CTRL+F: Popup Search Window
8. [ ] F1~F?: Mark translation Level (similar to xTranslate)

## Expand to Other Game Types.