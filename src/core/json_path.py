"""
A small, fast JSONPath-like path object.

Supports:
    JsonPath("$.store.book[0].title")
    JsonPath("store.book[0]['title']")
    JsonPath(["store", "book", 0, "title"])
    JsonPath(other_json_path)

    JsonPath(...) + JsonPath(...)
    JsonPath(...) + [ "more", 0, "parts" ]
    JsonPath(...) + "more[0].parts"

    path.parts -> list[str | int]
"""

import re
from typing import Iterable, Iterator, Union, Literal, Sequence

PathLike = Union["JsonPath", str, Sequence[Union[str, int]]]  # A type hint for anything that can be converted to a JsonPath

# One compiled regex, reused for every parse call. Alternation order matters:
# quoted-bracket forms are tried before the generic bareword-bracket fallback,
# and the numeric-bracket form is tried before bareword too, so `[0]` becomes
# an int and `['0']` / `["0"]` stay strings.
_TOKEN_RE = re.compile(
    r"""
    \.(?P<dot>[^.\[\]]+)                        # .key
  | \[\s*'(?P<squote>(?:[^'\\]|\\.)*)'\s*\]      # ['key'] (supports \' and \\)
  | \[\s*"(?P<dquote>(?:[^"\\]|\\.)*)"\s*\]      # ["key"]
  | \[\s*(?P<index>-?\d+)\s*\]                   # [0] / [-1]
  | \[\s*(?P<bare>[^\]]+?)\s*\]                  # [key]  (unquoted fallback)
    """,
    re.VERBOSE,
)

_ESCAPED_SQ = re.compile(r"\\(['\\])")
_ESCAPED_DQ = re.compile(r'\\(["\\])')



class JsonPath:
    """An immutable, hashable sequence of path parts."""

    __slots__ = ("_parts", "_parts_list_cache","__str_cache" )

    def __init__(self, source: PathLike = ()) -> None:
        if isinstance(source, JsonPath):
            self._parts = source._parts
        elif isinstance(source, (list, tuple)):
            self._parts = tuple(_validate_part(p) for p in source)
        elif isinstance(source, str):
            self._parts = _parse(source)
        else:
            raise TypeError(
                f"JsonPath() accepts JsonPath | list | tuple | str, got {type(source)!r}"
            )
        self.__str_cache = None
        self._parts_list_cache = None
    
    # -- fast internal constructor, skips validation/parsing entirely -------
    @classmethod
    def _from_parts(cls, parts: tuple, str_type: Literal["property", "array"]= "property") -> "JsonPath":
        obj = object.__new__(cls)
        obj._parts = parts
        obj.__str_cache = None
        obj._parts_list_cache = None
        return obj

    # -- public API -----------------------------------------------------
    @property
    def parts(self) -> list:
        """Materialize and cache the parts as a list (the tuple stays canonical)."""
        cached = self._parts_list_cache
        if cached is None:
            cached = list(self._parts)
            self._parts_list_cache = cached
        return cached

    def __add__(self, other: PathLike) -> "JsonPath":
        if isinstance(other, JsonPath):
            other_parts = other._parts
        elif isinstance(other, (list, tuple)):
            other_parts = tuple(_validate_part(p) for p in other)
        elif isinstance(other, str):
            other_parts = _parse(other)
        else:
            return NotImplemented
        return JsonPath._from_parts(self._parts + other_parts)

    def __radd__(self, other: PathLike) -> "JsonPath":
        if isinstance(other, (list, tuple)):
            return JsonPath._from_parts(tuple(_validate_part(p) for p in other) + self._parts)
        if isinstance(other, str):
            return JsonPath._from_parts(_parse(other) + self._parts)
        return NotImplemented

    # ---------------------------------------
    # !!!!! These will cause pandas to convert JsonPath to a tuple, causing unexpected behaviors
    # def __len__(self) -> int:
    #     return len(self._parts)

    # def __iter__(self) -> Iterator[Union[str, int]]:
    #     return iter(self._parts)

    # def __getitem__(self, item):
    #     result = self._parts[item]
    #     return JsonPath._from_parts(result) if isinstance(item, slice) else result
    # ---------------------------------------
    def __eq__(self, other) -> bool:
        if isinstance(other, JsonPath):
            return self._parts == other._parts
        if isinstance(other, (list, tuple)):
            return self._parts == tuple(other)
        return NotImplemented
    
    def __gt__(self, other) -> bool:
        if isinstance(other, JsonPath):
            return self._parts > other._parts
        if isinstance(other, (list, tuple)):
            return self._parts > tuple(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._parts)

    def __bool__(self) -> bool:
        return bool(self._parts)

    def __repr__(self) -> str:
        return f"JsonPath({self._parts!r})"
    
    
    def as_property_str(self) -> str:
        if self.__str_cache is None:
            self.__str_cache = _render(self._parts, "property")
        return self.__str_cache

    def as_array_str(self) -> str:
        return _render(self._parts, "array")

    def __str__(self) -> str:
        return self.as_property_str()

def _render(parts: Iterable[Union[str, int]], str_type: str) -> str:
    if str_type == 'array':
        out = ["$"]
        for p in parts:
            if isinstance(p, int):
                out.append(f"[{p}]")
            else:
                out.append(f"[{_quote(p)}]")
        return "".join(out)
    elif str_type == 'property':
        out = ["$"]
        for p in parts:
            if isinstance(p, int):
                out.append(f"[{p}]")
            elif p.isidentifier():
                out.append(f".{p}")
            else:
                out.append(f"[{_quote(p)}]")
        return "".join(out)
    else:
        raise ValueError(f"Invalid str_type: {str_type}")


def _validate_part(p):
    if isinstance(p, bool) or not isinstance(p, (str, int)):
        raise TypeError(f"Invalid JsonPath part {p!r}; expected str or int")
    return p

def _quote(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"

def _is_int(s: str) -> bool:
    return s.lstrip("-").isdigit() and s not in ("", "-")

def _parse(s: str) -> tuple:
    s = s.strip()
    if s in ("", "$"):
        return ()
    if s.startswith("$"):
        s = s[1:]
    # Normalize so the first segment can be matched by the same ".key" rule
    # as every later segment, unless it already opens with a "." or "[".
    if s and s[0] not in ".[":
        s = "." + s

    parts = []
    pos, length = 0, len(s)
    while pos < length:
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise ValueError(f"Invalid JsonPath syntax at position {pos} in {s!r}")
        if m["dot"] is not None:
            val = m["dot"]
            parts.append(int(val) if _is_int(val) else val)
        elif m["squote"] is not None:
            parts.append(_ESCAPED_SQ.sub(r"\1", m["squote"]))
        elif m["dquote"] is not None:
            parts.append(_ESCAPED_DQ.sub(r"\1", m["dquote"]))
        elif m["index"] is not None:
            parts.append(int(m["index"]))
        else:  # bare
            val = m["bare"]
            parts.append(int(val) if _is_int(val) else val)
        pos = m.end()
    return tuple(parts)