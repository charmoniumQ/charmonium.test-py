from __future__ import annotations
import dataclasses
import pathlib
import shutil
import subprocess
from typing import Mapping, Iterable

from ..util import hash_path, mime_type, file_type, hash_path, create_temp_dir, walk_files, random_str


@dataclasses.dataclass(frozen=True)
class File:
    hash_algo: str
    hash_bits: int
    hash_val: int
    size: int
    file_type: str
    mime_type: str
    url: pathlib.Path | None
    contents: bytes | None

    @staticmethod
    def from_path(path: pathlib.Path, url: pathlib.Path | None = None) -> File:
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"{path} is not a regular file")
        return File(
            hash_algo="xxhash",
            hash_bits=64,
            hash_val=hash_path(path, size=64),
            size=path.stat().st_size,
            file_type=file_type(path),
            mime_type=mime_type(path),
            url=path if url is None else url,
            contents=path.read_bytes(),
        )

    @staticmethod
    def blank() -> File:
        return File(
            hash_algo="xxhash",
            hash_bits=64,
            hash_val=hash_path(pathlib.Path("/dev/null", size=64)),
            size=0,
            file_type="empty",
            mime_type="inode/x-empty",
            url=None,
            contents=b"",
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, File):
            if self.hash_algo == other.hash_algo and self.hash_bits == other.hash_bits:
                return self.hash_val == other.hash_val
            else:
                raise ValueError("Files have different hash algorithms. No determination could be made.")
        else:
            return False

    def check_invariants(self) -> Iterable[UserWarning]:
        if not (0 <= self.hash_val < (1 << self.hash_bits)):
            yield UserWarning("hash is bigger than hash_bits", self, self.hash_val, self.hash_bits)
        if self.size < 0:
            yield UserWarning("File cannot have negative size")
        if self.contents is not None:
            assert len(self.contents) == self.size

    @property
    def empty(self) -> bool:
        return self.size == 0

    def read_bytes(self) -> bytes | None:
        """Return the bytes of this file, if we have them, else None."""
        if self.contents is not None:
            return self.contents
        else:
            raise RuntimeError("We didn't store the bytes of this file.")


@dataclasses.dataclass(frozen=True)
class FileBundle:
    archive: File | None
    files: Mapping[pathlib.Path, File]

    @staticmethod
    def from_path(data_path: pathlib.Path, compress: bool = False, move: bool = False) -> FileBundle:
        # TODO: make this be a true remote archive.
        contents: dict[pathlib.Path, File] = {}
        for path in walk_files(data_path, full_path=False):
            if (data_path / path).is_file() and not (data_path / path).is_symlink():
                contents[path] = File.from_path(data_path / path)
        if compress:
            assert move
            # This branch puts all of the files from data_path into an archive in a remote destination
            remote_archive = pathlib.Path(".cache2") / (random_str(10) + ".tar.xz")
            with create_temp_dir() as temp_dir:
                local_archive = temp_dir / remote_archive.name
                (temp_dir / "files").write_text(
                    "\n".join(
                        str(member.relative_to(data_path))
                        for member in data_path.iterdir()
                    ) + "\n"
                )
                cmd = ["tar", "--create", "--xz", f"--file={local_archive}", f"--files-from={temp_dir / 'files'}"]
                proc = subprocess.run(
                    cmd,
                    cwd=data_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                with local_archive.open("rb") as src_fileobj, remote_archive.open("wb") as dst_fileobj:
                    shutil.copyfileobj(src_fileobj, dst_fileobj)
                return FileBundle(File.from_path(local_archive, remote_archive), contents)
        elif move:
            # This branch puts all of the files from in a remote destination
            remote_archive = pathlib.Path(".cache2") / random_str(10)
            remote_archive.mkdir(parents=True)
            for path in contents.keys():
                (remote_archive / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(data_path / path, remote_archive / path)
            index_file = remote_archive / "index"
            index_file.write_text("\n".join(map(str, contents.keys())))
            return FileBundle(File.from_path(index_file), contents)
        else:
            # This branch puts all of the files into this object in RAM
            return FileBundle(None, contents)

    @staticmethod
    def blank() -> FileBundle:
        return FileBundle(None, {})

    def check_invariants(self) -> Iterable[UserWarning]:
        for file in self.files.values():
            yield from file.check_invariants()

    @property
    def empty(self) -> bool:
        return not bool(self.files)

    @property
    def size(self) -> int:
        return sum(file.size for file in self.files.values())
