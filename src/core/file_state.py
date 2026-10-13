from __future__ import annotations
import hashlib
from pathlib import Path
from typing import overload
from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class FileState:
    """Represents the state of a file, including its size, modification time, and SHA-256 hash."""
    size: int
    mtime_ns: int
    sha256: bytes

    @classmethod
    def from_path(cls, path: Path) -> FileState:
        stat = path.stat()
        with path.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").digest()
        return cls(stat.st_size, stat.st_mtime_ns, digest,)
    
    @overload
    def validate(self, other: FileState) -> bool: ...
    @overload
    def validate(self, other: Path) -> bool: ...
    @overload
    def validate(self, *, sha256: bytes, size: int) -> bool: ...
    @overload
    def validate(self, *, sha256: bytes, mtime_ns: int) -> bool: ...
    def validate(self, other: FileState|Path|None=None, *, sha256: bytes|None = None, size: int|None = None, mtime_ns: int|None = None) -> bool:
        """Validate the file state against another FileState, a Path, or specific attributes."""
        match other, sha256, size, mtime_ns:
            case FileState(), _, _, _:
                return self == other
            case Path(), _, _, _:
                return self == FileState.from_path(other)
            case None, bytes(), int(), None:
                return self.sha256 == sha256 and self.size == size
            case None, bytes(), None, int():
                return self.sha256 == sha256 and self.mtime_ns == mtime_ns
            case _:
                raise TypeError(f"Unsupported combination of arguments: {other}, {sha256}, {size}, {mtime_ns}")
            
    def quick_validate(self, other: FileState|Path) -> bool:
        """Validate the file state by comparing only size and mtime_ns, ignoring sha256."""
        if isinstance(other, FileState):
            return self.size == other.size and self.mtime_ns == other.mtime_ns
        if isinstance(other, Path):
            stat = other.stat()
            return self.size == stat.st_size and self.mtime_ns == stat.st_mtime_ns
        raise TypeError(f"Unsupported type: {type(other)}")