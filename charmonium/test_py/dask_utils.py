import datetime
import random
import pathlib
from typing import TYPE_CHECKING, Callable, TypeVar, Optional, cast
from typing_extensions import ParamSpec
import functools
import subprocess

import charmonium.cache

from . import config
from .util import create_temp_dir


Params = ParamSpec("Params")
Return = TypeVar("Return")


def call_if_cached(func: charmonium.cache.Memoized[Params, Return], *args: Params.args, **kwargs: Params.kwargs) -> tuple[bool, Optional[Return]]:
    """If function(input) hits in the cache, return (True, result), otherwise (False, None).

    This function does not mark the cache entry as accessed, count
    towards time saved, or write the index, because there is no
    analagous operation (call_if_cached) for an uncached function.

    That makes it fast.

    """

    call_id = random.randint(0, 2**64 - 1)
    key, entry, obj_key, value_ser = func._would_hit(call_id, *args, **kwargs)
    hit, value = False, None
    if entry is not None:
        if entry.obj_store:
            if value_ser is not None:
                hit, value = func._try_unpickle(value_ser, call_id)
        else:
            hit, value = True, cast(Return, entry.value)
    return hit, value
