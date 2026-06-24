from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    content_type: str
    size: int
    etag: str | None = None


class ObjectStorage(Protocol):
    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredObject:
        ...

    def get_bytes(self, key: str) -> bytes:
        ...

    def delete(self, key: str) -> None:
        ...

    def exists(self, key: str) -> bool:
        ...


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredObject:
        resolved_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        self._objects[key] = (bytes(data), resolved_type)
        return StoredObject(key=key, content_type=resolved_type, size=len(data))

    def get_bytes(self, key: str) -> bytes:
        return self._objects[key][0]

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._objects


class LocalFilesystemObjectStorage:
    """Filesystem-backed storage for development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Object key escapes storage root.")
        return path

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredObject:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        resolved_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        return StoredObject(key=key, content_type=resolved_type, size=len(data))

    def get_bytes(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()
