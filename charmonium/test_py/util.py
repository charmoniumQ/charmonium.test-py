import contextlib
import itertools
import os
import random
import pathlib
import string
import shutil

from typing import Generator, Iterable, TypeVar


def random_str(
        length: int,
        alphabet: str = string.ascii_lowercase + string.digits,
) -> str:
    return "".join(random.choice(alphabet) for _ in range(length))


def get_unused_path(prefix: pathlib.Path, candidates: Iterable[str]) -> pathlib.Path:
    for candidate in candidates:
        candidate_path = prefix / candidate
        if not candidate_path.exists():
            return candidate_path
    else:
        raise FileExistsError("No unused path")


tmp_root = pathlib.Path.home() / "tmp"


@contextlib.contextmanager
def create_temp_dir(cleanup: bool = True) -> Generator[pathlib.Path, None, None]:
    temp_dir = get_unused_path(tmp_root, (random_str(10) for _ in itertools.count()))
    temp_dir.mkdir(parents=True)
    os.sync()
    try:
        yield pathlib.Path(temp_dir)
    finally:
        if cleanup:
            shutil.rmtree(temp_dir)
            os.sync()


_T = TypeVar("_T")


def flatten1(elemss: Iterable[Iterable[_T]]) -> Iterable[_T]:
    for elems in elemss:
        for elem in elems:
            yield elem


def walk_files(path: pathlib.Path, full_path: bool = True) -> Iterable[pathlib.Path]:
    yield from _walk_files(path, path, full_path)


def _walk_files(
    path: pathlib.Path,
    root_path: pathlib.Path,
    full_path: bool,
) -> Iterable[pathlib.Path]:
    if path.is_dir():
        for subpath in path.iterdir():
            yield from _walk_files(subpath, root_path, full_path)
    else:
        if full_path:
            yield path
        else:
            yield path.relative_to(root_path)


def mtime(path: pathlib.Path) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(path.stat().st_mtime)
