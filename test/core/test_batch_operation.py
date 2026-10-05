import pandas as pd
from core.batch_operation import load_yaml, WhitespaceTrimer, PatternReplacer

yaml_repr = r"""
- OP: PYFORMAT_REGEX_REPLACE
  PATTERNS:
    # Keys are regex patterns, values follow python format strings.
    \[Accuracy\s*(?P<suffix>[^\(]*)(?P<size>\([A-Za-z]+\))\]:        '[命中率{suffix}{size}]'
    \[Evasion\s*(?P<suffix>[^\(]*)(?P<size>\([A-Za-z]+\))\]:         '[迴避率{suffix}{size}]'
    \[Magic(al)? Reduction (?P<size>\([A-Za-z]+\))\]:                '[魔法減免{size}]'
    \[Physical & Magic(al)? Reduction (?P<size>\([A-Za-z]+\))\]:     '[物理&魔法減免{size}]'
    \[Physical Reduction (?P<size>\([A-Za-z]+\))\]:                  '[物理減免{size}]'
    '\[Type: (?P<type>\w+)\]':                                       '[類型：{type}]'
  SUBPATTERNS: 
    # subpatterns are only used with OP=PYFORMAT_REGEX_REPLACE, and are used to replace named groups in the replacement string
    # due to implementation limitations, subpatterns currently take no regex matching.
    size:
      (small):  (S)
      (med):    (M)
      (medium): (M)
      (large):  (L)
    type:
      Lightwear:   輕甲
      Heavy Armor: 重甲
    # suffix: is not defined, so it will be left as is in the replacement string (similar to normal regex replacement with \g<suffix>)
- OP: REPLACE
  PATTERNS:
    "Sword": "刀劍"
"""
class TestBatchOperation:
    def test_pattern_replacer(self):
        """Test the PyFormatRegexReplacer operation."""
        op = PatternReplacer(
            PATTERNS={"long": "長", "sword": "劍", "axe": "斧"},
            REGEX=False, CASE=False
        )
        out = op(pd.Series(["long sword", "long axe", "short sword"]))
        assert out.tolist() == ["長 劍", "長 斧", "short 劍"], f"Unexpected output: {out}"
        
    def test_pyformat_regex_replacer(self):
        """Test the PyFormatRegexReplacer operation."""
        op = load_yaml(yaml_repr)[0]  # Load the first operation from the YAML
        test_series = pd.Series([
            "[Accuracy +(Small)][Evasion +(Medium)][Magic Reduction (Large)]",
            "[Accuracy +(Med)][Physical & Magical Reduction (Medium)]",
            "[Type: Lightwear]",
            "No match here"
        ])
        expected_output = pd.Series([
            "[命中率+(S)][迴避率+(M)][魔法減免(L)]",
            "[命中率+(M)][物理&魔法減免(M)]",
            "[類型：輕甲]",
            "No match here"
        ])
        result = op(test_series)
        assert result.equals(expected_output), f"Unexpected output:\n{result}"
    
    def test_trim_mono_whitespace(self):
        """Test the TrimWhitespace operation."""
        op = WhitespaceTrimer()
        test_series = pd.Series([
            "Will Be Trimmed.",
            "Double  spaced  not  trimmed.",
            "NoSpacesHere",
            "Multiple   spaces   between   words"
        ])
        expected_output = pd.Series([
            "WillBeTrimmed.",
            "Double  spaced  not  trimmed.",
            "NoSpacesHere",
            "Multiple   spaces   between   words"
        ])
        result = op(test_series)
        assert result.equals(expected_output), f"Unexpected output:\n{result}"
    def test_trim_all_whitespace(self):
        """Test the TrimWhitespace operation."""
        op = WhitespaceTrimer(ALL=True)
        test_series = pd.Series([
            "Will Be Trimmed.",
            "Double  spaced  is  trimmed.",
            "NoSpacesHere",
            "Multiple   spaces   between   words"
        ])
        expected_output = pd.Series([
            "WillBeTrimmed.",
            "Doublespacedistrimmed.",
            "NoSpacesHere",
            "Multiplespacesbetweenwords"
        ])
        result = op(test_series)
        assert result.equals(expected_output), f"Unexpected output:\n{result}"