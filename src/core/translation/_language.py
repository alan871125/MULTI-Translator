class Language(str):
    """A helper class to represent a language with both its name and code,
    allowing for more user-friendly display of language names while still keeping track of the underlying language code.
    Backwards compatible with str, so it can be used wherever a string is expected.
    """
    code: str
    is_source: bool = True
    is_target: bool = True
    def __new__(cls, code:str, name:str, is_source: bool = True, is_target: bool = True):
        """Create a new instance of Language with the given code and name.
        """
        instance = super().__new__(cls, name)
        instance.code = code
        instance.is_source = is_source
        instance.is_target = is_target
        return instance