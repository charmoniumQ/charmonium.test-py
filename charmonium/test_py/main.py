import dataclasses
import pathlib
import shutil
from typing import Iterable, TypeVar, Optional, Any, Sized, Union, Callable, Mapping, ParamSpec, cast

import dask
from charmonium.cache import memoize

from .util import create_temp_dir, flatten1
from .types import Code, Result, Condition, Registry, Analysis
from . import config


Return = TypeVar("Return")
Params = ParamSpec("Params")


def load_or_compute_remotely(func: Callable[Params, Return]) -> Callable[Params, Return]:
    memoized_func = memoize()(func)
    def outer_func(*args: Params.args, **kwargs: Params.kwargs) -> Return:
        if memoized_func.would_hit(*args, **kwargs):
            return memoized_func(*args, **kwargs)
        else:
            delayed_result = dask.delayed(memoized_func)(*args, **kwargs)  # type: ignore
            return cast(Return, delayed_result)
    return outer_func


@dataclasses.dataclass
class Config:
    registries: tuple[Registry, ...]
    conditions: tuple[Condition, ...]
    analyses: tuple[Analysis, ...]


def main(config: Config) -> list[Result]:
    # TODO: add aggregator, aggregates results (per-workflow analysis and inter-workflow analysis)
    codes = flatten1(
        dask.compute(
            tuple(
                dask.delayed(
                    memoize()(lambda: list(registry.get_codes()))
                )()
                for registry in config.registries
            )
        )
    )
    results: list[Result] = []
    for code in codes:
        # with create_temp_dir() as temp_path:
        #     code.checkout(temp_path)
        #     for condition in config.conditions:
        #         for analysis in config.analyses:
        #             results.append(analysis.analyze(code, condition, temp_path))
        print(code)
    results = dask.compute(results)[0]
    return results


from .registries import NfCoreRegistry, SnakemakeWorkflowCatalog
main(Config(
    registries=(SnakemakeWorkflowCatalog(),),
    conditions=(),
    analyses=(),
))
