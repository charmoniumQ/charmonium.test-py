import pathlib
from typing import TYPE_CHECKING, Callable, TypeVar
from typing_extensions import ParamSpec
import functools
import subprocess

import charmonium.cache

from . import config
from .util import create_temp_dir


Params = ParamSpec("Params")
Return = TypeVar("Return")


if TYPE_CHECKING:
    def delayed(func: Callable[Params, Return]) -> Callable[Params, Return]:
        return func
    def compute(*elem: Return) -> tuple[Return, ...]:
        return elem
else:
    from dask import delayed, compute


class DirObjStore(charmonium.cache.DirObjStore):
    def __init__(self, path: pathlib.Path, key_bytes: int = 16) -> None:
        self.path = path
        self.key_bytes = key_bytes

        if self.path.exists():
            if any(
                not self._is_key(path) and not path.name.startswith(".")
                for path in self.path.iterdir()
            ):
                raise ValueError(f"{self.path.resolve()} contains junk I didn't make.")
        else:
            self.path.mkdir(parents=True)


group = charmonium.cache.MemoizedGroup(
    size=config.cache_size,
    obj_store=DirObjStore(path=config.data_path() / "cache"),
    fine_grain_persistence=True,
)


def load_or_compute_remotely(func: Callable[Params, Return]) -> Callable[Params, Return]:
    memoized_func = charmonium.cache.Memoized(func=func, group=group)
    def outer_func(*args: Params.args, **kwargs: Params.kwargs) -> Return:
        if memoized_func.would_hit(*args, **kwargs):
            return memoized_func(*args, **kwargs)
        else:
            delayed_result = delayed(memoized_func)(*args, **kwargs)
            return delayed_result
    return outer_func
