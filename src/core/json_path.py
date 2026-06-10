import json

class JsonPath(str):
    @classmethod
    def from_list(cls, json_path_list: list[str|int]):
        return cls(json.dumps(json_path_list))
    def to_list(self):
        return json.loads(self)
    def __add__(self, other: 'JsonPath'):
        return JsonPath(self[:-1] + "," + other[1:])  # Combine two JSON paths by merging their list representations