from pathlib import Path
from typing import Iterable

class FileNode(Path):
    def __init__(self, path: str):
        super().__init__(path)
        self.next: FileNode | None = None # next is least recent 
        self.prev: FileNode | None = None # prev is more recent

class LeastRecentlyUsedFiles:
    def __init__(self, file_list: Iterable[str]|None = None, /, max_files: int = 10):
        self.max_files = max_files
        self.head: FileNode | None = None  # Least recently used file
        self.tail: FileNode | None = None  # Most recently used file
        self.file_map:dict[str, FileNode] = {}  # Map file paths to their corresponding nodes for O(1) access
        for file_path in (file_list or []):
            self.add_recent_file(file_path)
    
    def _move_to_tail(self, node: FileNode):
        if node is self.tail:
            return  # Already the most recently used file
        if node is self.head:
            self.head = node.next  # Update head if necessary
            if self.head:
                self.head.prev = None
        else:
            # Remove node from its current position
            if node.prev:
                node.prev.next = node.next
            if node.next:
                node.next.prev = node.prev
        
        # Move node to tail
        node.prev = self.tail
        node.next = None
        if self.tail:
            self.tail.next = node
        self.tail = node
        
        if not self.head:  # If the list was empty, set head to the new node
            self.head = node
            
    def add_recent_file(self, file_path: str|Path):
        file_path = Path(file_path).as_posix()  # Normalize the file path to a string
        if file_path in self.file_map:
            node = self.file_map[file_path]
            self._move_to_tail(node)
        else:
            new_node = FileNode(file_path)
            self.file_map[file_path] = new_node
            self._move_to_tail(new_node)
            
            if len(self.file_map) > self.max_files:
                # Remove the least recently used file
                if lru_node := self.head:
                    self.head = lru_node.next
                    if self.head:
                        self.head.prev = None
                    del self.file_map[lru_node.as_posix()]
    
    def iter(self, reverse: bool = False):
        current = self.tail if reverse else self.head
        while current:
            yield current
            current = current.prev if reverse else current.next
    
    def __iter__(self):
        return self.iter()        
    
    def to_list(self) -> list[str]:
        return [node.as_posix() for node in self]
        
