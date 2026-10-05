"""
Batch Operations for pandas Text Processing

Arguments in operation classes are Uppercase INTENTIONALY to show greater distinction between pattern keys.

"""
import yaml
from typing import Annotated, Literal, Union, Protocol
from pydantic import BaseModel, Field, RootModel
import pandas as pd

# class BatchOperation(Protocol):
#     """Protocol for batch operations that can be applied to a pandas Series."""
#     OP: str
#     def __call__(self, series: pd.Series) -> pd.Series: ...

class PatternReplacer(BaseModel):
    """An operation to replace text patterns in a pandas Series using regex or simple string replacement.
    
    Example:
    ```
        op = PatternReplacer(
            PATTERNS={"long": "長", "sword": "劍", "axe": "斧"},
            REGEX=False, CASE=False
        )
        out = op(pd.Series(["long sword", "long axe", "short sword"]))
        # output: ["長 劍", "長 斧", "short 劍"]
    """
    OP: Literal["REPLACE"] = "REPLACE"
    PATTERNS: dict[str, str]
    REGEX: bool = False  
    CASE: bool = False  
    def __call__(self, series: pd.Series) -> pd.Series:
        for pattern, replacement in self.PATTERNS.items():
            # series.str.replace instead of series.replace to ensure substring replacements
            series = series.str.replace(pattern, replacement, regex=self.REGEX, case=self.CASE)
        return series
    
class PyFormatRegexReplacer(BaseModel):
    r"""A Special Operation to Replace patterns in a pandas Series using Regex->Python format strings.
    
    - `PATTERNS` are regex patterns with named groups, and the replacement strings are Python format strings that can reference those named groups.
    - `SUBBPATERNS` are used to replace named groups in the replacement string
    - Due to implementation limitations, `SUBBPATERNS` currently take no regex matching.
    Example:
        ```
        op = PyFormatRegexReplacer(
            PATTERNS={
                r"\[Accuracy\s*(?P<suffix>[^\(]*)(?P<size>\([A-Za-z]+\))\]": "[命中率{suffix}{size}]"
            },
            SUBPATTERNS={
                "size": {
                    "(small)": "(S)",
                    "(med)": "(M)",
                    "(medium)": "(M)", # you can't use regex in subpatterns, so you need to define all variations
                    "(large)": "(L)"
                }
            }
        )
        out = op(pd.Series(["[Accuracy +(Small)]", "[Accuracy +(Medium)]", "[Accuracy +(Large)]"]))
        # Output: ["[命中率+(S)]", "[命中率+(M)]", "[命中率+(L)]"]
        ```
    """
    OP: Literal["PYFORMAT_REGEX_REPLACE"] = "PYFORMAT_REGEX_REPLACE"
    PATTERNS: dict[str, str]
    # SUBPATTERNS is required or optional specifically for this operation type
    SUBPATTERNS: dict[str, dict[str, str]] = Field(default_factory=dict)
    CASE: bool = False
    def get_lambda_replacement(self, repl):
        def repl_func(match):
            group_dict = match.groupdict()
            for k, v in group_dict.items():
                if (v_repl := self.SUBPATTERNS.get(k, {}).get(v))  is None:
                    # Get the replacement from subpatterns if it exists
                    v_repl = self.SUBPATTERNS.get(k, {}).get(v.lower(), v)
                group_dict[k] = v_repl            
            return repl.format(**group_dict)  # Use the updated group_dict to format the replacement string
        return repl_func
    
    def __call__(self, series: pd.Series) -> pd.Series:
        for pattern, replacement in self.PATTERNS.items():
            series = series.str.replace(pattern, self.get_lambda_replacement(replacement), regex=True, case=self.CASE)
        return series

class WhitespaceTrimer(BaseModel):
    """Trim single whitespaces between words.
    
    Could be useful when translating from languages that use single spaces between words (e.g., English, Spanish) to languages that don't (e.g., Chinese, Japanese).
    
    Example:
        ```
        out = TrimWhitespace()(pd.Series(["Will Be Trimmed.", "Double  spaced  not  trimmed."]))
        # output: ["WillBeTrimmed.", "Double  spaced  not  trimmed."]
        ```
    """
    OP: Literal["TRIM_WHITESPACE"] = "TRIM_WHITESPACE"
    ALL: bool = False  # If True, trims all whitespace, not just single spaces between words
    def __call__(self, series: pd.Series) -> pd.Series:
        if self.ALL:
            return series.replace(r'\s+', '', regex=True)
        else:
            return series.replace(r'\b\s\b', '', regex=True)


# Discriminator union: Pydantic inspects 'OP' to decide which model to parse
BatchOperation = Annotated[
    Union[PatternReplacer, PyFormatRegexReplacer, WhitespaceTrimer],
    Field(discriminator="OP"),
]

# Parse as a list of discriminated union items
BatchPatternList = RootModel[list[BatchOperation]]
def load_yaml(yaml_repr: str) -> list[BatchOperation]:
    """Reads a YAML string containing batch patterns and returns a list of BatchPattern objects."""
    return BatchPatternList.model_validate(yaml.safe_load(yaml_repr)).root
