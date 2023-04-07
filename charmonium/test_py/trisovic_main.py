import datetime
import pathlib
from typing import TYPE_CHECKING, Callable, TypeVar, ParamSpec

import requests
import charmonium.cache

from .analyses.measure_command_execution import CompletedContainer, measure_docker_execution
from .analyses.file_bundle import FileBundle
from .util import create_temp_dir
from . import config


Params = ParamSpec("Params")
Return = TypeVar("Return")


if TYPE_CHECKING:
    def delayed(func: Callable[Params, Return]) -> Callable[Params, Return]:
        return func
    def compute(*elem: Return) -> tuple[Return, ...]:
        return elem
else:
    from dask import delayed, compute


group = charmonium.cache.MemoizedGroup(
    size="10GiB",
    obj_store=charmonium.cache.DirObjStore(path=config.data_path() / "cache"),
    fine_grain_persistence=True,
)


@charmonium.cache.memoize(group=group)
def get_dois() -> list[str]:
    return requests.get("https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/get-dois/dataset_dois.txt").text.strip().split("\n")


@charmonium.cache.memoize(group=group)
def analyze(doi: str) -> tuple[CompletedContainer, FileBundle]:
    with create_temp_dir() as temp_dir:
        proc = measure_docker_execution(
            "trisovic-runner:",
            ("./run_analysis.sh", doi, "", str(temp_dir)),
            wall_time_limit=datetime.timedelta(minutes=30),
            mem_limit=1024**3,
            cpus=1.0,
            readwrite_mounts=((temp_dir, pathlib.Path("/results")),),
            readonly_binds=(pathlib.Path("~/.docker/config.json"),),
        )
        result = FileBundle.from_path(temp_dir, compress=False)
        return proc, result


if __name__ == "__main__":
    dois = get_dois()
    analyze(dois[0])
