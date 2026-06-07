from utils import walk_json

def test_walk_json():
    data = {"a": 1, "b": {"c": 2}}
    result = list(walk_json(data))
    expected = [ # DFS order
        (1, ["a"], data),
        (2, ["b", "c"], {"c": 2}),
        ({"c": 2}, ["b"], data),
    ]
    for r, e in zip(result, expected):
        print(r)
        assert r == e, f"Expected {e}, got {r}"