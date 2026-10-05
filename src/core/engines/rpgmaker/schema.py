from core.json_path import JsonPath

# Represents the fields that contain translatable text in various RPG Maker data files. 
# The key represents the file stem (without extension), and the value is a list of fields within that file that contain text to be translated.
TRANSLATION_FIELDS = {
    "Actors": ["name", "nickname", "profile"],
    "Armors": ["name", "description"],
    "Items":  ["name", "description"],
    "Classes": ["name"],
    "Enemies": ["name"],
    "Skills": ["name", "description"],
}

# Represents the event codes that contain translatable text in RPG Maker event data (found in CommonEvents.json and Map*.json event data).
EVENT_TRANSLATION_CODES = {
    102: "ShowChoices",
    108: "Comment",
    401: "Text",
    402: "ChoiceBranch",
    408: "Comment",
    357: "PluginCommand",
    122: "ControlVariables"
}

# If a code 357 is found, the corresponding handler will be used to extract the text from the parameters
PLUGIN_HANDLERS:dict[tuple[str, str], JsonPath] = { 
    ("MNKR_TMLogWindowMZ", 'addLog'): JsonPath("$.text"),
    ("DTextPicture", 'dText'): JsonPath("$.text"),
}