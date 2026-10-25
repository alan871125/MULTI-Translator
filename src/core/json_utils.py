import json
from typing import Any, Generator

class JSONWithCommentsDecoder(json.JSONDecoder):
    def __init__(self, **kw):
        super().__init__(**kw)

    def decode(self, s: str, _w = Any) -> Any:
        s = '\n'.join(l if not l.lstrip().startswith('//') else '' for l in s.split('\n'))
        return super().decode(s, _w)

def walk_json(data: Any, /, path:list=[], parent:Any=None) -> Generator[tuple[Any, list, Any], None, None]:
    """
    Walk through a JSON structure and yield each value along with its path and parent.
    
    Returns:
        A generator that yields a tuple of (value, path, parent) for each value in the JSON structure.
        - value: The current value in the JSON structure.
        - path: A list representing the path to the current value in the JSON structure.
        - parent: The parent object (dict or list) of the current value.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            yield from walk_json(v, path + [k], data)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            yield from walk_json(v, path + [i], data)
    else:
        yield data, path, parent