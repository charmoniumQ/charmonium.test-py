import dataclasses
import pathlib
import shutil
from typing import Iterable, TypeVar, Any, Callable, Mapping, ParamSpec, cast, TYPE_CHECKING

from charmonium.cache import memoize, Memoized, MemoizedGroup
import tqdm

from .util import create_temp_dir, flatten1
from .types import Code, Result, Condition, Registry, Analysis
from . import config


Return = TypeVar("Return")
Params = ParamSpec("Params")


if TYPE_CHECKING:
    def delayed(func: Callable[Params, Return]) -> Callable[Params, Return]:
        return func
    def compute(*elem: Return) -> tuple[Return, ...]:
        return elem
    def ignore_arg(obj: Return) -> Return:
        return obj
else:
    from dask import delayed, compute
    import wrapt
    class ignore_arg(wrapt.ObjectProxy):
        def __getfrozenstate__(self):
            return None


group = MemoizedGroup(size="10GiB")


def load_or_compute_remotely(func: Callable[Params, Return]) -> Callable[Params, Return]:
    memoized_func = Memoized(func=func, group=group)
    def outer_func(*args: Params.args, **kwargs: Params.kwargs) -> Return:
        if memoized_func.would_hit(*args, **kwargs):
            return memoized_func(*args, **kwargs)
        else:
            delayed_result = delayed(memoized_func)(*args, **kwargs)
            return delayed_result
    return outer_func


@dataclasses.dataclass
class Config:
    registries: tuple[Registry, ...]
    conditions: tuple[Condition, ...]
    analyses: tuple[Analysis, ...]


def main(config: Config) -> list[Result]:
    # TODO: add aggregator, aggregates results (per-workflow analysis and inter-workflow analysis)
    @memoize(group=group)
    def get_codes(registry) -> list[Code]:
        return list(registry.get_codes())

    codes = list(flatten1(
        get_codes(registry)
        for registry in config.registries
    ))

    get_codes.log_usage_report()

    @memoize(group=group)
    def analyze(analysis: Analysis, code: Code, condition: Condition) -> Result:
        with create_temp_dir() as temp_path:
            code.checkout(temp_path)
            return analysis.analyze(code, condition, temp_path)

    results: list[Result] = []
    for analysis in config.analyses:
        for code in tqdm.tqdm(codes[1:2]):
            for condition in config.conditions:
                results.append(analyze(analysis, code, condition))

    analyze.log_usage_report()

    # results = compute(results)[0]

    return results


if __name__ == "__main__":
    from .registries import TrisovicDataverseFixed
    from .analyses import ExecuteWorkflow

    main(Config(
        registries=(TrisovicDataverseFixed(),),
        conditions=(Condition(),),
        analyses=(ExecuteWorkflow(),),
    ))
