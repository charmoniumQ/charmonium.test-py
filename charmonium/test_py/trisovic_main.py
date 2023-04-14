import datetime
import pathlib
from typing import TYPE_CHECKING, Callable, TypeVar

import requests
import charmonium.cache

from .analyses.measure_command_execution import CompletedContainer, measure_docker_execution
from .analyses.file_bundle import FileBundle
from .util import create_temp_dir
from . import config


if TYPE_CHECKING:
    from typing_extensions import ParamSpec
    Params = ParamSpec("Params")
    Return = TypeVar("Return")
    def delayed(func: Callable[Params, Return]) -> Callable[Params, Return]:
        return func
    def compute(*elem: Return) -> tuple[Return, ...]:
        return elem
else:
    Params = None
    Return = None
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
    size="10GiB",
    obj_store=DirObjStore(path=config.data_path() / "cache"),
    fine_grain_persistence=True,
)


@charmonium.cache.memoize(group=group)
def get_dois() -> list[str]:
    return requests.get("https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/get-dois/dataset_dois.txt").text.strip().split("\n")


image = "wfregtest.azurecr.io/trisovic-runner:commit-8d2dddb7-1681241078"


@charmonium.cache.memoize(group=group)
def analyze(doi: str) -> tuple[CompletedContainer, FileBundle]:
    with create_temp_dir() as temp_dir:
        proc = measure_docker_execution(
            image,
            ("./run_analysis.sh", doi, "", str(temp_dir)),
            wall_time_limit=datetime.timedelta(minutes=30),
            mem_limit=1024**3,
            cpus=1.0,
            readwrite_mounts=((temp_dir, pathlib.Path("/results")),),
            readonly_binds=(pathlib.Path("~/.docker/config.json").expanduser(),),
        )
        result = FileBundle.from_path(temp_dir, compress=False)
        return proc, result


if __name__ == "__main__":
    import pickle
    dois = get_dois()
    for doi in dois[:10]:
        proc, result = analyze(doi)
        print(doi)
        if proc.exit_code != 0:
            print("return != 0", proc)
        print("proc len", len(pickle.dumps(proc)))
        print("files size", result.size)
        run_log = pathlib.Path("run_log.csv")
        if run_log in result.files and (run_log_txt := result.files[run_log].contents) is not None:
            print(run_log_txt.decode())
        else:
            print("No run log")
        print()
