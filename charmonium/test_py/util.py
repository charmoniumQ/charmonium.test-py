import types
import tempfile
import contextlib
import itertools
import datetime
import docker  # type: ignore
import os
import random
import pathlib
import string
import shutil
import shlex
import urllib.parse
import subprocess
import xml.etree.ElementTree
from typing import Generator, Iterable, TypeVar, Any, Mapping, TypeGuard, TYPE_CHECKING, cast


def fs_escape(string: str) -> str:
    return urllib.parse.quote(string.replace(" ", "-").replace("_", "-"), safe="")


def random_str(
        length: int,
        alphabet: str = string.ascii_lowercase,
) -> str:
    return "".join(random.choice(alphabet) for _ in range(length))


def get_unused_path(prefix: pathlib.Path, candidates: Iterable[str]) -> pathlib.Path:
    for candidate in candidates:
        candidate_path = prefix / candidate
        if not candidate_path.exists():
            return candidate_path
    else:
        raise FileExistsError("No unused path")


# Note that paths in /tmp won't work.
# see https://github.com/sylabs/singularity/issues/1331
# Also note, this path should be mounted from the container to the host in the exact same path.
if pathlib.Path("/my-tmp").exists():
    tmp_root = pathlib.Path("/my-tmp")
elif not tempfile.gettempdir().startswith("/tmp"):
    tmp_root = pathlib.Path(tempfile.gettempdir())
else:
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


def file_type(path: pathlib.Path) -> str:
    return subprocess.run(["file", "--brief", str(path)], capture_output=True, text=True, check=True).stdout.strip()


def mime_type(path: pathlib.Path) -> str:
    return subprocess.run(["file", "--brief", "--mime-type", str(path)], capture_output=True, text=True, check=True).stdout.strip()


def hash_path(path: pathlib.Path | str | bytes, size: int = 128) -> int:
    import xxhash
    hasher = {
        128: xxhash.xxh128(),
        64: xxhash.xxh64(),
        32: xxhash.xxh32(),
    }[size]
    block_size = 1 << 14
    with open(path, "rb") as file:
        while True:
            buffer = file.read(block_size)
            if not buffer:
                break
            hasher.update(buffer)
    return hasher.intdigest()


def expect_type(typ: type[_T] | types.UnionType, data: Any) -> _T:
    if not isinstance(data, typ):
        raise TypeError(f"Expected type {typ} for {data}, but got {type(data)}")
    return data  # type: ignore


def xml_to_tuple(elem: xml.etree.ElementTree.Element) -> tuple[str, Mapping[str, str], str | None, tuple[Any, ...]]:
    text = elem.text.strip() if elem.text else ""
    tail = elem.tail.strip() if elem.tail else ""
    children = tuple(xml_to_tuple(child) for child in elem)
    return (
        elem.tag,
        dict(elem.attrib.items()),
        (text + tail if text + tail else None),
        (children if children else ()),
    )


def chown(path: pathlib.Path) -> None:
    image = "busybox"
    command = (
        "chown",
        f"{os.getuid()}:{os.getgid()}",
        "-R",
        "/work",
    )
    container = docker.from_env().containers.run(
        image=image,
        command=command,
        volumes={
            str(path): {
                "bind": "/work",
                "mode": "rw",
            },
        },
        detach=True,
    )
    result = container.wait()
    if result["StatusCode"] != 0:
        raise RuntimeError(f"`docker run {shlex.join(command)}` failed with {result['StatusCode']}. See `docker logs {container.id}`")
    container.remove(force=True)


if TYPE_CHECKING:
    def ignore_arg(obj: _T) -> _T:
        return obj
else:
    import wrapt
    class ignore_arg(wrapt.ObjectProxy):
        def __getfrozenstate__(self) -> None:
            return None


from typing import Callable, TypeVar
from typing_extensions import ParamSpec
import charmonium.cache
FuncParams = ParamSpec("FuncParams")
FuncReturn = TypeVar("FuncReturn")
def clear_cache(
        fn: charmonium.cache.Memoized[FuncParams, FuncReturn],
        *args: FuncParams.args,
        **kwargs: FuncParams.kwargs,
) -> None:
    key, entry, obj_key, value_ser = fn._would_hit(0, *args, **kwargs)
    if entry is not None:
        fn.group._deleter((key, entry))
    assert not fn.would_hit(*args, **kwargs)


import re
from typing import Optional
def find_last(
        pattern: re.Pattern[str],
        haystack: str,
) -> Optional[re.Match[str]]:
    original_match = None
    original_idx = 0
    while True:
        next_match = pattern.search(haystack, original_idx)
        if next_match is None:
            return original_match
        else:
            original_match = next_match
            original_idx = next_match.start()


def is_not_none(x: Optional[_T]) -> TypeGuard[_T]:
    return x is not None


def parse_one_bracketed_expression(
        string: str,
        brackets: Mapping[str, str] = {"(": ")"},
) -> str:
    if not string:
        raise SyntaxError("Cannot find bracketed expression from empty string")
    if string[0] not in brackets:
        raise SyntaxError(f"String does not start with a bracket: {string}")
    stack = [string[0]]
    for i, char in zip(range(1, len(string)), string[1:]):
        if char in brackets:
            stack.append(char)
        elif char == brackets[stack[-1]]:
            stack.pop()
        if not stack:
            return string[1:i]
    raise SyntaxError(f"Unmatched left-brackets {stack} in {string}")


def return_args(function: Callable[FuncParams, FuncReturn]) -> Callable[FuncParams, tuple[FuncParams.args, FuncParams.kwargs, FuncReturn]]:
    def actual_function(*args: FuncParams.args, **kwargs: FuncParams.kwargs) -> tuple[FuncParams.args, FuncParams.kwargs, FuncReturn]:
        return (args, kwargs, function(*args, **kwargs))
    return actual_function


assert return_args(fs_escape)("hello world") == (("hello world",), {}, "hello-world")
