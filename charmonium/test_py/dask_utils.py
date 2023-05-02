import pathlib
from typing import TYPE_CHECKING, Callable, TypeVar
from typing_extensions import ParamSpec
import functools
import subprocess

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


def load_or_compute_remotely(func: Callable[Params, Return]) -> Callable[Params, Return]:
    memoized_func = charmonium.cache.Memoized(func=func, group=config.memoized_group)
    def outer_func(*args: Params.args, **kwargs: Params.kwargs) -> Return:
        if False and memoized_func.would_hit(*args, **kwargs):
            return memoized_func(*args, **kwargs)
        else:
            delayed_result = delayed(memoized_func)(*args, **kwargs)
            return delayed_result
    return outer_func
