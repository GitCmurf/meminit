"""Local filesystem adapter implementing FileSystemPort."""
import pathlib

from meminit.core.ports import FileSystemPort


class LocalFileSystem:
    """Concrete filesystem adapter using pathlib.Path."""

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return pathlib.Path(path).read_text(encoding=encoding)

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        pathlib.Path(path).write_text(content, encoding=encoding)

    def exists(self, path: str) -> bool:
        return pathlib.Path(path).exists()

    def is_file(self, path: str) -> bool:
        return pathlib.Path(path).is_file()

    def is_dir(self, path: str) -> bool:
        return pathlib.Path(path).is_dir()

    def resolve(self, path: str) -> str:
        return str(pathlib.Path(path).resolve())

    def mkdir(self, path: str, parents: bool = True, exist_ok: bool = True) -> None:
        pathlib.Path(path).mkdir(parents=parents, exist_ok=exist_ok)

    def iterdir(self, path: str) -> list[str]:
        return [str(p) for p in pathlib.Path(path).iterdir()]

    def read_bytes(self, path: str) -> bytes:
        return pathlib.Path(path).read_bytes()

    def write_bytes(self, path: str, data: bytes) -> None:
        pathlib.Path(path).write_bytes(data)
