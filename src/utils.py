import json
from typing import Any
class JSONWithCommentsDecoder(json.JSONDecoder):
    def __init__(self, **kw):
        super().__init__(**kw)

    def decode(self, s: str) -> Any:
        s = '\n'.join(l if not l.lstrip().startswith('//') else '' for l in s.split('\n'))
        return super().decode(s)


def walk_json(d, path=[], parent=None):
    # represent keys as strings with quotes, and list indices as integer strings, 
    # so that the path can be easily used to locate the item in the original JSON structure for replacement
    if isinstance(d, dict):
        for k, v in d.items():
            # yield from walk_json(v, path + [f'"{k}"'], d)
            yield from walk_json(v, path + [k], d)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            # yield from walk_json(v, path + [str(i)], d)
            yield from walk_json(v, path + [i], d)
    else:
        yield d, path, parent