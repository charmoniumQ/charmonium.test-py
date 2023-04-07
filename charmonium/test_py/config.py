import logging
import os
import pathlib
import functools
from typing import Any

import azure.identity.aio
import charmonium.cache
import charmonium.freeze
import distributed
import docker  # type: ignore
import github
import upath

for logger_name in ["charmonium.cache.perf", "charmonium.cache.ops", "charmonium.freeze"]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    fname = pathlib.Path(logger.name.replace(".", "_") + ".log")
    if fname.exists() and len(fname.read_text()) > 1024 * 256:
        fname.unlink()
    fh = logging.FileHandler(fname)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.debug("Program %d", os.getpid())

for config in [charmonium.cache.freeze_config, charmonium.freeze.global_config]:
    config.ignore_classes.update({
        ("git.cmd", "Git"),
        ("git.repo", "Repo"),
        ("subprocess", "Popen"),
        ("gitdb.util", "LazyMixin"),
        ("git.db", "GitCmdObjectDB"),
        ("gitdb.db.loose", "LooseObjectDB"),
        ("gitdb.db.base", "FileDBBase"),
        ("git.config", "GitConfigParser"),
        ("git.config", "write"),
        ("configparser", "RawConfigParser"),
        ("configparser", "NoOptionError"),
        ("configparser", "Error"),
        ("git.objects.submodule.base", "Submodule"),
        ("git.objects.commit", "Commit"),
        ("git.refs.head", "Head"),
        ("git.refs.symbolic", "SymbolicReference"),
        ("git.refs.reference", "Reference"),
        ("git.refs.remote", "RemoteReference"),
        ("git.refs.tag", "TagReference"),
        ("git.remote", "Remote"),
        ("git.repo.base", "Repo"),
        ("requests.sessions", "Session"),
        ("collections.abc", "MutableMapping"),
        ("dataclasses", "_MISSING_TYPE"),
        ("dataclasses", "Field"),
        ("dataclasses", "_FIELD_BASE"),
        ("dataclasses", "_DataclassParams"),
        ("charmonium.time_block.time_block", "TimeBlock"),
        ("aiohttp.client", "ClientSession"),
        ("asyncio.coroutines", "CoroWrapper"),
    })
    config.ignore_objects_by_class.update({
            ("charmonium.time_block.time_block", "TimeBlock"),
    })
    config.ignore_functions.update({
        ("requests.api", "get"),
        ("git.cmd", "is_cygwin"),
        ("git.repo.base", "__init__"),
        ("git.repo.base", "_clone"),
        ("json", "loads"),
        ("subprocess", "run"),
        ("platform", "node"),
        ("platform", "platform"),
        ("shutil", "rmtree"),
        ("shutil", "copy"),
        ("shutil", "move"),
        ("charmonium.time_block.time_block", "ctx"),
        ("asyncio.runners", "run"),
        ("asyncio.tasks", "gather"),
    })


# azure.identity.aio.DefaultIdentityCredential is not picklable.
# So, instead we create a surrogate object that initializes a new DefaultIdentityCredential when it gets restored from Pickle.
# __init__ implicitly calls azure.identity.aio.ManagedIdentityCredential.__init__
# __setstate__ also calls azure.identity.aio.ManagedIdentityCredential.__init__
# __getstate__ is dummy that returns something Truthy.
class AzureCredential(azure.identity.aio.DefaultAzureCredential):
    def __getstate__(self) -> str:
        return "hi" # must be Truthy
    def __setstate__(self, state: Any) -> None:
        azure.identity.aio.DefaultAzureCredential.__init__(self)


def data_path() -> pathlib.Path:
    return pathlib.Path() / ".cache2"
    # return upath.UPath(
    #     "abfs://data4/",
    #     account_name="wfregtest",
    #     credential=AzureCredential(),
    # )


def index_path() -> pathlib.Path:
    return pathlib.Path() / ".cache"
    # return upath.UPath(
    #     "abfs://index4/",
    #     account_name="wfregtest",
    #     credential=AzureCredential(),
    # )


def harvard_dataverse_token() -> str:
    return os.environ.get("HARVARD_DATAVERSE_TOKEN", "")


@functools.cache
def docker_client() -> docker.DockerClient:
    return docker.from_env()


@functools.cache
def github_client() -> github.Github:
    return github.Github(os.environ.get("GITHUB_ACCESS_TOKEN", None))


@functools.cache
def dask_client() -> distributed.Client:
    return distributed.Client(  # type: ignore
            address="127.0.0.1:8786",
    )
