import collections
import pickle
import dataclasses
import itertools
import pathlib
import shlex
import shutil
import io
import traceback
import sys
import textwrap
from typing import Iterable, TypeVar, Any, Callable, Mapping, cast, TYPE_CHECKING, Optional

import toolz  # type: ignore
import tqdm
import charmonium.cache
import dask
import distributed

from .util import create_temp_dir, flatten1, expect_type
from .types import Code, Result, Condition, Registry, Analysis
from . import config


@dataclasses.dataclass
class Config:
    registries: tuple[Registry, ...]
    conditions: tuple[Condition, ...]
    analyses: tuple[Analysis, ...]
    first_n: Optional[int] = None
    # TODO: add aggregator, aggregates results (per-workflow analysis and inter-workflow analysis)


@charmonium.cache.memoize(group=config.memoized_group())
def get_codes(registry: Registry) -> list[Code]:
    return list(registry.get_codes())


@charmonium.cache.memoize(group=config.memoized_group())
def analyze(analysis: Analysis, code: Code, condition: Condition, iteration: int) -> tuple[Code, Condition, Analysis, Result | Exception]:
    with create_temp_dir() as temp_path:
        with charmonium.time_block.ctx("checkout"):
            try:
                code.checkout(temp_path)
            except Exception as exc:
                return (code, condition, analysis, exc)
        with charmonium.time_block.ctx("analyze"):
            try:
                result = analysis.analyze(code, condition, temp_path)
                try:
                    pickle.dumps(result)
                except Exception as exc:
                    print(result)
                    raise exc
                return (code, condition, analysis, result)
            except Exception as exc:
                return (code, condition, analysis, exc)


def stream_results(
        dask_client: distributed.Client,
        experimental_config: Config,
) -> tuple[int, Iterable[tuple[Code, Condition, Analysis, Result | Exception]]]:
    codes = list(flatten1(
        get_codes(registry)
        for registry in experimental_config.registries
    ))
    if experimental_config.first_n is not None:
        codes = codes[:experimental_config.first_n]

    n_futures = len(experimental_config.analyses) * len(codes) * len(experimental_config.conditions)

    analyses, codes, conditions, iterations = zip(*itertools.product(experimental_config.analyses, codes, experimental_config.conditions, range(1)))

    analyses_tqdm = tqdm.tqdm(analyses, desc="Jobs submitted", total=n_futures)

    results_stream = cast(
        Iterable[tuple[Code, Condition, Analysis, Result | Exception]],
        map(
            toolz.second,
            distributed.as_completed(
                dask_client.map(analyze, analyses_tqdm, codes, conditions, iterations),
                with_results=True,
            ),
        ),
    )
    return n_futures, results_stream


@charmonium.cache.memoize(group=config.memoized_group())
def get_results(
        experimental_config: Config,
) -> list[tuple[Code, Condition, Analysis, Result | Exception]]:
    delayed_analyze = dask.delayed(analyze)

    codes = list(flatten1(
        get_codes(registry)
        for registry in experimental_config.registries
    ))

    if experimental_config.first_n is not None:
        codes = codes[:experimental_config.first_n]

    return cast(
        list[tuple[Code, Condition, Analysis, Result | Exception]],
        dask.compute(*map(
            delayed_analyze,
            *zip(*itertools.product(experimental_config.analyses, codes, experimental_config.conditions, range(1))),
        )),
    )


if __name__ == "__main__":
    from .registries import DataverseTrisovicFixed
    from .analyses import ExecuteWorkflow, WorkflowExecution
    from .codes import WorkflowCode, DataverseDataset
    from .codes.dataverse_dataset import HashMismatchError

    dask_client = config.dask_client()
    experimental_config = Config(
        registries=(DataverseTrisovicFixed(),),
        conditions=(Condition(),),
        analyses=(ExecuteWorkflow(),),
        first_n=4000,
    )

    def print_result(result: WorkflowExecution) -> None:
        for label, filebundle in [("outputs", result.outputs), ("logs", result.logs)]:
            for path, file in filebundle.files.items():
                print(
                    f"  {path} size={file.size} ({label})",
                    textwrap.indent(
                        expect_type(bytes, file.contents[:1000]).decode(errors="backslashreplace"),
                        prefix=" " * 4,
                    ),
                    sep="\n",
                )
        for label, std_bytes in [("stdout", result.proc.stdout_b), ("stderr", result.proc.stderr_b)]:
            print(
                f"  {label}:",
                textwrap.indent(
                    std_bytes.decode(errors="backslashreplace"),
                    prefix=" " * 4,
                ),
                sep="\n",
            )
        print()

    from typing import Callable, TypeVar
    from typing_extensions import ParamSpec
    FuncParams = ParamSpec("FuncParams")
    FuncReturn = TypeVar("FuncReturn")
    def clear_cache(
            fn: charmonium.cache.Memoized[FuncParams, FuncReturn],
            *args: FuncParams.args,
            **kwargs: FuncParams.kwargs,
    ) -> None:
        key, entry, obj_key, value_ser = fn._would_hit(0, *args, **kwargs)
        fn._deleter((key, entry))
        assert not fn.would_hit(*args, **kwargs)

    print("Config loaded")

    results = get_results(experimental_config)

    # n_results, results_stream = stream_results(dask_client, experimental_config)
    # results = tqdm.tqdm(
    #     results_stream,
    #     desc="jobs completed",
    #     total=n_results,
    # )

    result_status = collections.Counter()
    result_script_status = collections.Counter()

    for n, (code, condition, analysis, result) in enumerate(results):
        if isinstance(code, WorkflowCode) and isinstance(code.code, DataverseDataset):
            name = code.code.persistent_id
        else:
            name = str(code)
        if isinstance(result, WorkflowExecution):
            if result.proc.exit_code == 0:
                results_file = result.outputs.files.get(pathlib.Path("index"), None)
                if results_file is not None and (contents := results_file.contents) is not None:
                    any_missing_files = False
                    any_failures = False
                    all_successes = True
                    any_files = False
                    for line in filter(bool, contents.decode().strip().split("\n")):
                        any_files = True
                        results_str, _space, r_file = line.partition(" ")
                        results_path = pathlib.Path(results_str)
                        expected_files = {results_path / "status", results_path / "stdout", results_path / "stderr"}
                        missing_files = expected_files - result.outputs.files.keys()
                        if missing_files:
                            any_mising_files = True
                            # print(f"{name} mising files {missing_files}")
                            # print_result(result)
                        else:
                            status = 0 == int(expect_type(bytes, result.outputs.files[results_path / "status"].contents).decode())
                            if not status:
                                any_failures = True
                                all_successes = False
                                result_script_status["failure"] += 1
                                # print(f"{name} script failed {r_file}")
                                # print(expect_type(bytes, result.outputs.files[results_path / "stderr"].contents).decode(errors="backslashreplace"))
                            else:
                                result_script_status["successes"] += 1
                                # print("success")
                                pass
                    if not any_files:
                        result_status["no R scripts"] += 1
                    elif any_missing_files:
                        result_status["missing files"] += 1
                    elif any_failures:
                        result_status["all normal; some scripts fail"] += 1
                    elif all_successes:
                        result_status["all scripts succeed"] += 1
                    else:
                        raise RuntimeError("Exhausted cases")
                else:
                    print(f"{name} no result index")
                    result_status["no result index"] += 1
                    print_result(result)
            else:
                print(f"{name} docker command failed")
                print_result(result)
                result_status["docker command failed"] += 1
        elif isinstance(result, HashMismatchError):
            #print(f"{name} hash_mismatch:", textwrap.indent(str(result), prefix="  "), sep="\n")
            result_status["hash mismatch"] += 1
        elif isinstance(result, Exception):
            print(f"{name} exception {result.__class__.__name__}")
            print(textwrap.indent("\n".join(traceback.format_exception(result)), prefix="  "))
            result_status["exception in runner"] += 1
            clear_cache(analyze, analysis, code, condition, 0)
            clear_cache(get_results, experimental_config)
        else:
            raise TypeError("Exhausted cases")
        if n % 30 == 0:
            print(result_status, result_status.total())
            print(result_script_status, result_script_status.total())
    print(result_status, result_status.total())
    print(result_script_status, result_script_status.total())
