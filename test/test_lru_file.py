import pytest
from core.lru_file import LeastRecentlyUsedFiles

class TestLRUFiles:
    @pytest.fixture
    def test_init(self):
        file_list = ["file1.txt", "file2.txt", "file3.txt"]
        lru = LeastRecentlyUsedFiles(file_list, max_files=3)
        assert [node.as_posix() for node in lru.iter()] == file_list
        return lru

    def test_init_from_cls(self, test_init):
        lru = LeastRecentlyUsedFiles(test_init)
        assert list(lru) == list(test_init), "Initialization from another LRU instance should preserve the order of files."
        
    def test_init_empty_list(self):
        lru = LeastRecentlyUsedFiles([])
        assert lru.to_list() == [], "to_list should return an empty list for an empty LRU."
        self.test_add2empty_list(lru, "file1.txt")  # Test adding to the empty LRU after initialization
    
    def test_add2empty_list(self, lru:LeastRecentlyUsedFiles|None=None, file_path="file1.txt"):
        if lru is None:
            lru = LeastRecentlyUsedFiles(max_files=3)
        assert lru.head is None and lru.tail is None, "Head/Tail not None. Supposedly an error in test setup."
        lru.add_recent_file(file_path)
        assert lru.head is not None and lru.tail is not None, "After adding a file, head and tail should not be None."
        assert lru.head.as_posix() == lru.tail.as_posix() == file_path, "After adding the first file, head and tail should point to the same file."
        assert lru.to_list() == [file_path], "to_list should return a list with the single added file."    
    
    def test_add_and_iterate_files(self):
        lru = LeastRecentlyUsedFiles(max_files=3)
        self.test_add2empty_list(lru, "file1.txt")  # Start with one file in the LRU
        lru.add_recent_file("file2.txt")
        assert [node.as_posix() for node in lru.iter()] == ["file1.txt", "file2.txt"]
        lru.add_recent_file("file3.txt")
        # Check order of files (most recent last)
        assert [node.as_posix() for node in lru.iter()] == ["file1.txt", "file2.txt", "file3.txt"]
        
        # Check that head and tail are correct
        assert lru.head is not None and lru.tail is not None, "After adding files, head and tail should not be None."
        assert lru.head.as_posix() == "file1.txt", "Head should point to the least recently used file."
        assert lru.tail.as_posix() == "file3.txt", "Tail should point to the most recently used file."
        
    def test_access_file_moves_to_tail(self):
        lru = LeastRecentlyUsedFiles(max_files=3)
        lru.add_recent_file("file1.txt")
        lru.add_recent_file("file2.txt")
        lru.add_recent_file("file3.txt")
        
        # Access file1.txt again, it should move to the tail (most recent)
        lru.add_recent_file("file1.txt")
        assert [node.as_posix() for node in lru.iter()] == ["file2.txt", "file3.txt", "file1.txt"]
    def test_exceeding_max_files(self):
        lru = LeastRecentlyUsedFiles(max_files=3)
        lru.add_recent_file("file1.txt")
        lru.add_recent_file("file2.txt")
        lru.add_recent_file("file3.txt")
        # Adding a new file should remove the least recently used one (file1.txt)
        lru.add_recent_file("file4.txt")
        assert [node.as_posix() for node in lru.iter()] == ["file2.txt", "file3.txt", "file4.txt"]
    
    def test_settings_integration(self):
        from app.settings import SettingsData
        
        # 1. Test that when loading settings with recent files being empty, it initializes correctly
        settings = SettingsData(**{"recent_files":[]}) # Test __init__ typing
        (lru:=settings.recent_files).add_recent_file("file1.txt")
        lru.add_recent_file("file1.txt")
        assert ((lru.head is not None and lru.tail is not None) and 
                lru.head.as_posix() == lru.tail.as_posix() == "file1.txt"), "After adding the first file, head and tail should point to the same file."
        
        # 2. Test that when loading settings with recent files, it initializes correctly
        settings = SettingsData.model_validate({"recent_files":["file1.txt", "file2.txt", "file3.txt"]})
        (lru:=settings.recent_files).add_recent_file("file1.txt")
        assert lru.to_list() == ["file2.txt", "file3.txt", "file1.txt"], "After accessing file1.txt, it should move to the end of the list."
        lru.add_recent_file("file2.txt")
        lru.add_recent_file("file3.txt")
        assert lru.to_list() == ["file1.txt", "file2.txt", "file3.txt"], "After accessing file2.txt and file3.txt, they should move to the end of the list in order."
        # Check that adding a new file removes the least recently used one
        lru.add_recent_file("file4.txt")
        assert lru.to_list() == ["file1.txt", "file2.txt", "file3.txt", "file4.txt"]