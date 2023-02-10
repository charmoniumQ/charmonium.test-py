import dataclasses
from pathlib import Path
import urllib.parse
from typing import Iterable, TypeVar, Optional, Any, Sized, Union, Callable, Mapping, ParamSpec, cast
import shutil

from dask.bag import from_sequence, concat  # type: ignore
#from charmonium.cache import memoize
import locket  # type: ignore
from tqdm import tqdm  # type: ignore

from .util import get_unused_path
from .types import Project, Version, Result, Condition, ProjectRegistry


_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., Any])


def memoize() -> Callable[[_F], _F]:
    def inner(func: _F) -> _F:
        def new_func(*args: Any, **kwargs: Any) -> _T:
            return cast(_T, func(*args, **kwargs))
        return cast(_F, new_func)
    return inner


@dataclasses.dataclass
class Config:
    test: Callable[[Version, Condition, Path, int, int], Result]
    conditions: tuple[Condition]
    global_path: Optional[Path] = None
    local_path: Path = Path("/tmp/wf-reg-test")
    project_result: Optional[Callable[[Result], Result]] = None
    project_registries: tuple[ProjectRegistry, ...] = ()
    npartitions: int = 100


def ignore_arg(elem: _T) -> _T:
    raise NotImplementedError


def test_one(version: Version, condition: Condition, config: Config) -> Result | Exception:
    # TODO: worker_id
    worker_id = 0
    total_workers = 0
    worker_cache_path = config.local_path / str(worker_id)
    worker_cache_path.mkdir(exist_ok=True, parents=True)
    private_project_path = get_unused_path(worker_cache_path)
    # TODO: Think about reusing global state or not?
    # if config.global_cache_path:
    #     global_project_path = config.global_cache_path /  urllib.parse.quote_plus(version.project.get_unique_name())
    #     with locket(global_project_path.with_suffix(".lock")):
    #         if not global_project_path.exists():
    #             version.clone(global_project_path.with_suffix(".code"))
    #             version.install_environment(global_project_path.with_suffix(".env"))
    #     shutil.copytree(global_project_path.with_suffix(".code"), private_project_path.with_suffix(".code"))
    #     shutil.copytree(global_project_path.with_suffix(".env"), private_project_path.with_suffix(".env"))
    #     version.checkout(private_project_path.with_suffix(".code"))
    #     env = version.update_environment(private_project_path.with_suffix(".env"))
    # else:
    if True:
        version.checkout(private_project_path.with_suffix(".code"))
    try:
        # TODO: cache test without private_project_path
        return memoize()(config.test)(
            ignore_arg(private_project_path),
        )
    # TODO: Should we delete the directory when done?
    except Exception as exc:
        return exc


def identity(elem: _T) -> _T:
    return elem


def main(config: Config) -> list[Result]:
    # TODO: Think about caching in a human-editable way.
    return cast(
        list[Result],
        (
            from_sequence(config.project_registries, parition_size=1)
            .map(memoize()(lambda registry: registry.get_projects()))
            .repartition(npartitions=config.npartitions)
            .map(memoize()(lambda project: project.get_versions()))
            .repartition(npartitions=config.npartitions)
            .product(from_sequence(Config.conditions, npartitions=1))
            .starmap(test_one, config=config)
            .map((config.project_result if config.project_result is not None else identity))
            .compute()
        )
    )
