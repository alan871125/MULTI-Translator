import json

class JsonPath(str):
    def __new__(cls, value: str|list[str|int]):
        if isinstance(value, list):
            return super().__new__(cls, json.dumps(value))
        if isinstance(value, str):
            try:
                json.loads(value)  # Validate if it's a valid JSON string
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON string: {value}")
        return super().__new__(cls, value)
    @property
    def parts(self)-> list[str|int]:
        return json.loads(self)  # Parse the JSON string back to a list of parts
    def __add__(self, other: 'JsonPath'):
        return JsonPath(self.parts + other.parts)  # Combine two JSON paths by merging their list representations
    def __repr__(self):
        return f"JsonPath({self.parts})"
    def __eq__(self, other):
        if isinstance(other, list):
            return self.parts == other
        else:
            return super().__eq__(other)
    def __hash__(self):
        return super().__hash__()