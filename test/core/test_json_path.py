from core.json_path import JsonPath
import pytest

@pytest.fixture
def samples():
    return {
        'property_style_str': JsonPath('$.key1.key2[0]'),
        'array_style_str': JsonPath('$["key1"]["key2"][0]'),
        'property_style_str_no_root': JsonPath('key1.key2[0]'),
        'array_style_str_no_root': JsonPath('["key1"]["key2"][0]'),
        'mixed_style_str': JsonPath('$.key1["key2"][0]'),
        'list': JsonPath(["key1", "key2", 0]),
        'tuple': JsonPath(("key1", "key2", 0)),
    }
    
class TestJsonPath:
    
    def test_init(self, samples):
        # Test initialization with a valid JSON string
        for key, path in samples.items():
            assert path.parts == ["key1", "key2", 0], f"Initialization with {key} should produce a JsonPath instance"
        # Test initialization with another JsonPath
        assert JsonPath(samples['property_style_str']) == samples['property_style_str'], "Initialization with another JsonPath should work"
    
    def test_addition(self, samples):
        path0 = JsonPath('key0')
        path1 = samples['property_style_str']
        combined_path0 = path0+path1
        assert isinstance(combined_path0, JsonPath), "Addition of two JsonPaths should return a JsonPath instance"
        assert combined_path0.parts == ["key0", "key1", "key2", 0] == list(path0.parts+path1.parts), "Addition of two JsonPaths should combine their parts"

        # Test addition with a list
        combined_path1_l = path0 + ["key1", "key2", 0]
        combined_path1_r = ['key0'] + path1
        assert combined_path1_l.parts == ["key0", "key1", "key2", 0], "Addition  with a list should combine parts correctly"
        assert combined_path1_r.parts == ["key0", "key1", "key2", 0], "Addition (right) with a list should combine parts correctly"
        
        # Test addition with a string
        combined_path2_l = path0 + "key1"
        combined_path2_r = "key0" + path1
        assert combined_path2_l.parts == ["key0", "key1"], "Addition with a string should combine parts correctly"
        assert combined_path2_r.parts == ["key0", "key1", "key2", 0], "Addition (right) with a string should combine parts correctly"
        
    def test_equality(self, samples):
        other_path = JsonPath('$.key1.key2[0]')
        for key, path in samples.items():
            assert path == other_path, f"Equality check failed for {key}"
        
    
    def test_hash(self, samples):
        parts = ('key1', 'key2', 0)
        for key, path in samples.items():
            assert hash(path) == hash(parts), f"Hash check failed for {key}"
        