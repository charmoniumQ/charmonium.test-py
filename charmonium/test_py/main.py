import random
import pickle
import dataclasses
import itertools
from typing import Iterable, TypeVar, Any, Callable, Mapping, cast, TYPE_CHECKING, Optional

import toolz  # type: ignore
import tqdm
import charmonium.cache
import dask
import distributed

from .util import create_temp_dir, flatten1, expect_type, return_args
from .types import Code, Result, Condition, Registry, Analysis, Reduction, ReducedResult
from . import config


@dataclasses.dataclass
class Config:
    registries: tuple[Registry, ...]
    conditions: tuple[Condition, ...]
    analysis: Analysis
    reduction: Reduction
    sample_size: Optional[int] = None
    seed: int = 0
    n_repetitions: int = 1
    # TODO: add aggregator, aggregates results (per-workflow analysis and inter-workflow analysis)


@charmonium.cache.memoize(group=config.memoized_group())
def get_codes(registry: Registry) -> list[Code]:
    return list(registry.get_codes())


@charmonium.cache.memoize(group=config.memoized_group())
def analyze(analysis: Analysis, code: Code, condition: Condition, iteration: int) -> Result | Exception:
    with create_temp_dir() as temp_path:
        with charmonium.time_block.ctx("checkout"):
            try:
                code.checkout(temp_path)
            except Exception as exc:
                return exc
        with charmonium.time_block.ctx("analyze"):
            try:
                return analysis.analyze(code, condition, temp_path)
            except Exception as exc:
                return exc


@charmonium.cache.memoize(group=config.memoized_group())
def reduced_analysis(reduction: Reduction, analysis: Analysis, code: Code, condition: Condition, iteration: int) -> ReducedResult | Exception:
    result_or_exc = analyze(analysis, code, condition, iteration)
    if isinstance(result_or_exc, Result):
        reduced_result = reduction.reduce(code, condition, result_or_exc)
        return reduced_result
    else:
        return result_or_exc


def stream_results(
        dask_client: distributed.Client,
        experimental_config: Config,
) -> tuple[int, Iterable[tuple[Code, Condition, ReducedResult | Exception]]]:
    codes = list(flatten1(
        get_codes(registry)
        for registry in experimental_config.registries
    ))
    if experimental_config.sample_size is not None:
        random.seed(experimental_config.seed)
        codes = random.sample(codes, experimental_config.sample_size)

    reductions: Iterable[Reduction]
    analyses: Iterable[Analysis]
    codes2: Iterable[Code]
    conditions: Iterable[Condition]
    iterations: Iterable[int]
    reductions, analyses, codes2, conditions, iterations = zip(*itertools.product(
        [experimental_config.reduction],
        [experimental_config.analysis],
        codes,
        experimental_config.conditions,
        range(experimental_config.n_repetitions),
    ))

    # Put one argument through tqdm to get a progress bar
    # As each code gets consumed, we know one job was submitted
    n_futures = len(codes) * len(experimental_config.conditions) * experimental_config.n_repetitions
    codes3 = tqdm.tqdm(codes2, desc="Jobs submitted", total=n_futures)


    stream = cast(
        Iterable[tuple[Any, tuple[tuple[Reduction, Analysis, Code, Condition, int], Mapping[str, Any], ReducedResult | Exception]]],
        distributed.as_completed(  # type: ignore
            dask_client.map(
                return_args(reduced_analysis),
                reductions,
                analyses,
                codes3,
                conditions,
                iterations,
            ),  # type: ignore
            with_results=True,
        ),
    )
    stream2 = (
        (code, condition, result)
        for future, ((reduction, analysis, code, condition, iteration), kwargs, result) in stream
    )
    return n_futures, stream2


@charmonium.cache.memoize(group=config.memoized_group())
def get_results(
        experimental_config: Config,
) -> list[tuple[Code, Condition, ReducedResult | Exception]]:
    codes = list(flatten1(
        get_codes(registry)
        for registry in experimental_config.registries
    ))

    if experimental_config.sample_size is not None:
        random.seed(experimental_config.seed)
        codes = random.sample(codes, experimental_config.sample_size)

    reductions: Iterable[Reduction]
    analyses: Iterable[Analysis]
    codes2: Iterable[Code]
    conditions: Iterable[Condition]
    iterations: Iterable[int]
    reductions, analyses, codes2, conditions, iterations = zip(*itertools.product(
        [experimental_config.reduction],
        [experimental_config.analysis],
        codes,
        experimental_config.conditions,
        range(experimental_config.n_repetitions),
    ))

    return cast(
        list[tuple[Code, Condition, ReducedResult | Exception]],
        list(
            zip(
                codes,
                conditions,
                dask.compute(*map(  # type: ignore
                    dask.delayed(reduced_analysis),  # type: ignore
                    reductions,
                    analyses,
                    codes2,
                    conditions,
                    iterations,
                )),
            ),
        ),
    )
