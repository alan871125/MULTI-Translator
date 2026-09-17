import pandas as pd
from typing import Literal

IndexLikeSequence = list[str]|list[int]|pd.Index
SearchableColumn = Literal["file", "key", "original", "translation"]


if __name__ == "__main__":
    # Example usage
    def foo(idxs: IndexLikeSequence):
        df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        df.loc[idxs, 'A'] = 10
        return pd.Index(idxs)
    
    