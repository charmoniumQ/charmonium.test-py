import dataclasses
import pathlib
import shutil
import io
import traceback
import sys
import textwrap
from typing import Iterable, TypeVar, Any, Callable, Mapping, cast, TYPE_CHECKING, Optional

import tqdm
import charmonium.cache
import dask

from .util import create_temp_dir, flatten1, expect_type
from .types import Code, Result, Condition, Registry, Analysis
from . import config
from .dask_utils import load_or_compute_remotely, compute


@dataclasses.dataclass
class Config:
    registries: tuple[Registry, ...]
    conditions: tuple[Condition, ...]
    analyses: tuple[Analysis, ...]
    first_n: Optional[int] = None
    # TODO: add aggregator, aggregates results (per-workflow analysis and inter-workflow analysis)


@charmonium.cache.memoize(group=config.memoized_group)
def get_codes(registry: Registry) -> list[Code]:
    return list(registry.get_codes())


@charmonium.cache.memoize(group=config.memoized_group)
def analyze(analysis: Analysis, code: Code, condition: Condition) -> tuple[Code, Condition, Analysis, Result | Exception]:
    with create_temp_dir() as temp_path:
        print("Checking out:", code)
        try:
            code.checkout(temp_path)
        except Exception as exc:
            return (code, condition, analysis, exc)
        print("Analyzing:", code)
        try:
            result = analysis.analyze(code, condition, temp_path)
            return (code, condition, analysis, result)
        except Exception as exc:
            return (code, condition, analysis, exc)


if __name__ == "__main__":
    from .registries import DataverseTrisovicFixed
    from .analyses import ExecuteWorkflow, WorkflowExecution
    from .codes import WorkflowCode, DataverseDataset
    import dask.distributed

    dask_client = config.dask_client()
    dask_client.run(__import__, "charmonium.test_py.config")

    experimental_config = Config(
        registries=(DataverseTrisovicFixed(),),
        conditions=(Condition(),),
        analyses=(ExecuteWorkflow(),),
        first_n=20,
    )

    print("Config loaded")

    codes = list(flatten1(
        get_codes(registry)
        for registry in tqdm.tqdm(experimental_config.registries, desc="registries scanned")
    ))

    if experimental_config.first_n is not None:
        codes = codes[:experimental_config.first_n]

    result_futures: list[Any] = []
    for code in tqdm.tqdm(codes, desc="jobs submitted"):
        for condition in experimental_config.conditions:
            for analysis in experimental_config.analyses:
                result_futures.append(cast(Any, dask_client.submit(analyze, analysis, code, condition)))

    results_stream = cast(
        Iterable[tuple[Any, tuple[Code, Condition, Analysis, Result | Exception]]],
        dask.distributed.as_completed(result_futures, with_results=True),  # type: ignore
    )
    results_stream = tqdm.tqdm(results_stream, desc="jobs completed", total=len(codes))

    for _future, (code, _condition, _analysis, result) in results_stream:
        if isinstance(code, WorkflowCode) and isinstance(code.code, DataverseDataset):
            name = code.code.persistent_id
        else:
            name = str(code)
        if isinstance(result, WorkflowExecution):
            if result.proc.exit_code == 0:
                results_file = result.outputs.files.get(pathlib.Path("index"), None)
                if results_file is not None and (contents := results_file.contents) is not None:
                    for line in contents.decode().strip().split("\n"):
                        results_str, _space, r_file = line.partition(" ")
                        results_path = pathlib.Path(results_str)
                        expected_files = {results_path / "status", results_path / "stdout", results_path / "stderr"}
                        missing_files = expected_files - result.outputs.files.keys()
                        if missing_files:
                            print(f"{name},mising files,{missing_files}")
                            for path, file in {**result.outputs.files, **result.logs.files}.items():
                                print(str(path), file.size)
                                print(expect_type(bytes, file.contents).decode())
                                print()
                            print("stdout:\n", result.proc.stdout_b.decode(), "\n")
                            print("stderr:\n", result.proc.stderr_b.decode(), "\n")
                            print()
                        status = 0 == int(expect_type(bytes, result.outputs.files[results_path / "status"].contents).decode())
                        if not status:
                            # print(f"{name},script failed,{r_file}")
                            # print(expect_type(bytes, result.outputs.files[results_path / "stderr"].contents).decode())
                            # print(expect_type(bytes, result.outputs.files[results_path / "stdout"].contents).decode())
                            # print()
                            pass
                        else:
                            # print("success")
                            pass
                else:
                    print(f"{name},no result index")
                    for path, file in {**result.outputs.files, **result.logs.files}.items():
                        print(str(path), file.size)
                        print(expect_type(bytes, file.contents).decode())
                        print()
                    print("stdout:\n", result.proc.stdout_b.decode(), "\n")
                    print("stderr:\n", result.proc.stderr_b.decode(), "\n")
                    print()
            else:
                print(f"{name},docker command failed")
                # print(result.proc.docker_command)
                # print(result.proc.stdout_b.decode())
                # print(result.proc.stderr_b.decode())
                print()
        elif isinstance(result, Exception):
            print(f"{name},exception,{result.__class__.__name__}")
            # traceback.print_exception(result)
            # traceback.print_tb(result.__traceback__)
            # print()
        else:
            raise TypeError()
