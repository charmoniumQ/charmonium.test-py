import dataclasses
import pathlib
import shutil
from typing import Iterable, TypeVar, Optional, Any, Sized, Union, Callable, Mapping, ParamSpec, cast, TYPE_CHECKING
from charmonium.cache import memoize, Memoized, MemoizedGroup

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
else:
    from dask import delayed, compute


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
    codes = list(flatten1(
        Memoized(func=lambda: list(registry.get_codes()), group=group)()
        for registry in config.registries
    ))
    results: list[Result] = []
    for code in codes:
        # with create_temp_dir() as temp_path:
        #     code.checkout(temp_path)
        #     for condition in config.conditions:
        #         for analysis in config.analyses:
        #             results.append(analysis.analyze(code, condition, temp_path))
        pass
    print(len(codes))
    results = compute(results)[0]
    return results


if __name__ == "__main__":
    import datetime
    import json
    import os
    import sys
    import csv
    from .registries import TrisovicDataverseFixed
    from .util import walk_files, mtime
    from .analyses.measure_command_execution import measure_docker_execution
    codes = list(TrisovicDataverseFixed().get_codes())
    for code in codes:
        with create_temp_dir() as temp_dir:
            code_dir = temp_dir / "code"
            out_dir = temp_dir / "out"
            code.checkout(code_dir)
            os.sync()
            start_time = datetime.datetime.now()
            container = measure_docker_execution(
                "r-runner",
                ("Rscript", "/exec_r_files.R", str(code_dir)),
                wall_time_limit=datetime.timedelta(hours=1),
                mem_limit=1024 * 1024 * 1024,
                cpus=1.0,
                readwrite_mounts=(temp_dir,),
            )
            if container.status != 0:
                files = {}
                for file_obj_json in (code_dir / "metrics.txt").read_text().split("\n"):
                    file_obj = json.loads(file_obj_json)
                    files["filename"] = file_obj
                with (code_dir / "run_log.csv").open() as f:
                    for dir, file, error in csv.reader(f):
                        files[file]["error"] = error
                for src in newer_files(code_dir):
                    if src.is_file() and mtime(src) >= start_time:
                        dst = out_dir / src.relative_to(root)
                        dst.parent.mkdir(exist_ok=True, parents=True)
                        shutil.move(src, dst)
                container.stdout_b
                container.stderr_b
            else:
                sys.stdout.buffer.write(container.stdout_b)
                sys.stderr.buffer.write(container.stderr_b)

    # main(Config(
    #     registries=(TrisovicDataverseFixed(),),
    #     conditions=(),
    #     analyses=(),
    # ))
