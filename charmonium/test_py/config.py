import warnings
import copy
import logging
import itertools
import os
import uuid
from types import TracebackType
import pathlib
import functools
import hashlib
import platform
import ssl
from typing import Any, Optional, Mapping

import azure.core.credentials
import azure.identity.aio
import azure.storage.blob
import certifi
import charmonium.cache
import charmonium.freeze
import dask.distributed
import docker  # type: ignore
import github
import upath
import charmonium.cache

for logger_name in ["charmonium.cache.perf", "charmonium.cache.ops", "charmonium.freeze"]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    fname = pathlib.Path(f"{logger.name.replace('.', '_')}.log")
    try:
        if fname.exists() and fname.stat().st_size > 1024 * 256:
            fname.unlink()
    except FileNotFoundError:
        pass
    fh = logging.FileHandler(fname)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)


freeze_config = copy.deepcopy(charmonium.cache.DEFAULT_FREEZE_CONFIG)
freeze_config.hash_length = 128
freeze_config.hasher = charmonium.freeze.config.HasherFromHashlibHasher(hashlib.blake2s, 128)
freeze_config.ignore_classes.update({
    ("git.cmd", "Git"),
    ("git.db", "GitCmdObjectDB"),
    ("git.config", "GitConfigParser"),
    ("git.config", "write"),
    ("git.objects.submodule.base", "Submodule"),
    ("git.objects.commit", "Commit"),
    ("git.refs.head", "Head"),
    ("git.refs.symbolic", "SymbolicReference"),
    ("git.refs.reference", "Reference"),
    ("git.refs.remote", "RemoteReference"),
    ("git.refs.tag", "TagReference"),
    ("git.remote", "Remote"),
    ("git.repo", "Repo"),
    ("git.repo.base", "Repo"),
    ("gitdb.util", "LazyMixin"),
    ("gitdb.db.loose", "LooseObjectDB"),
    ("gitdb.db.base", "FileDBBase"),
    ("collections.abc", "MutableMapping"),
    ("configparser", "RawConfigParser"),
    ("configparser", "NoOptionError"),
    ("configparser", "Error"),
    ("requests.sessions", "Session"),
    ("subprocess", "Popen"),
    ("dataclasses", "_MISSING_TYPE"),
    ("dataclasses", "Field"),
    ("dataclasses", "_FIELD_BASE"),
    ("dataclasses", "_DataclassParams"),
    ("charmonium.time_block.time_block", "TimeBlock"),
    ("aiohttp.client", "ClientSession"),
    ("asyncio.coroutines", "CoroWrapper"),
    ("charmonium.test_py.analyses.measure_command_execution.CompletedContainer", "CompletedContainer"),
})
freeze_config.ignore_objects_by_class.update({
    ("charmonium.time_block.time_block", "TimeBlock"),
})
freeze_config.ignore_functions.update({
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
    ("charmonium.test_py.analyses.file_bundle", "from_path"),
    ("charmonium.test_py.analyses.measure_command_execution", "measure_docker_execution"),
    ("charmonium.test_py.analyses.execute_workflow", "analyze"),
})


# azure.identity.aio.DefaultIdentityCredential is not picklable.
# So, instead we create a surrogate object that initializes a new DefaultIdentityCredential when it gets restored from Pickle.
# __init__ implicitly calls azure.identity.aio.ManagedIdentityCredential.__init__
# __setstate__ also calls azure.identity.aio.ManagedIdentityCredential.__init__
# __getstate__ is dummy that returns something Truthy.
class AzureAsyncCredential(azure.identity.aio.DefaultAzureCredential):
    def __init__(self) -> None:
        azure.identity.aio.DefaultAzureCredential.__init__(self)

    def __getstate__(self) -> str:
        return "hi" # must be Truthy

    def __setstate__(self, state: Any) -> None:
        azure.identity.aio.DefaultAzureCredential.__init__(self)


class AzureSyncCredential(azure.identity.DefaultAzureCredential):
    def __init__(self) -> None:
        azure.identity.DefaultAzureCredential.__init__(self)

    def __getstate__(self) -> str:
        return "hi" # must be Truthy

    def __setstate__(self, state: Any) -> None:
        azure.identity.DefaultAzureCredential.__init__(self)


def data_path() -> pathlib.Path:
    _data_path = upath.UPath(
        "abfs://data4/",
        account_name="wfregtest",
        credential=AzureAsyncCredential(),
    )
    return _data_path


def index_path() -> pathlib.Path:
    return upath.UPath(
        "abfs://index4/",
        account_name="wfregtest",
        credential=AzureAsyncCredential(),
    )


def harvard_dataverse_token() -> str:
    return os.environ.get("HARVARD_DATAVERSE_TOKEN", "")


@functools.cache
def docker_client() -> docker.DockerClient:
    return docker.from_env()


@functools.cache
def github_client() -> github.Github:
    return github.Github(os.environ.get("GITHUB_ACCESS_TOKEN", None))


@functools.cache
def dask_client() -> dask.distributed.Client:
    if platform.node() == "laptop":
        return dask.distributed.Client()  # type: ignore
    else:
        return dask.distributed.Client(address="tcp://manager:9000")  # type: ignore


@functools.cache
def ssl_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(certifi.where())
    return context


class AzureLock(charmonium.cache.Lock):
    def __init__(
            self,
            account_name: str,
            container_name: str,
            blob_name: str,
            credential: azure.core.credentials.TokenCredential,
            lease_duration: int = -1,
    ) -> None:
        self.blob = azure.storage.blob.BlobClient(
            f"https://{account_name}.blob.core.windows.net",
            container_name,
            blob_name,
            credential=credential,
        )
        if not self.blob.exists():
            self.blob.upload_blob(data=b"hello world", overwrite=True)
        self.lease = None
        self.lease_duration = lease_duration
        self.lease_id = uuid.uuid4()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            "account_name": self.blob.account_name,
            "container_name": self.blob.container_name,
            "blob_name": self.blob.blob_name,
            "credential": self.blob.credential,
            "lease_duration": self.lease_duration,
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        AzureLock.__init__(
            self,
            account_name=state["account_name"],
            container_name=state["container_name"],
            blob_name=state["blob_name"],
            credential=state["credential"],
            lease_duration=state["lease_duration"],
        )

    def __enter__(self) -> Optional[bool]:
        for retry in itertools.count():
            if retry > 10 and (retry % 10) == 0:
                warnings.warn(f"Going on {retry}th attempt. There is a lot of contention on this lock: {self.blob.blob_name}")
            try:
                self.lease = self.blob.acquire_lease(self.lease_duration, self.lease_id)
                print(self.lease_id, "acquired")
                return
            except azure.core.exceptions.ResourceExistsError:
                pass

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        assert self.lease is not None, "Must call __enter__ before __exit__"
        print(self.lease_id, "release")
        self.lease.release()
        self.lease = None


memoized_group = charmonium.cache.MemoizedGroup(
    size="100GiB",
    obj_store=charmonium.cache.DirObjStore(path=data_path() / "cache"),
    fine_grain_persistence=True,
    freeze_config=freeze_config,
    lock=charmonium.cache.NaiveRWLock(AzureLock(
        account_name="wfregtest",
        container_name="data4",
        blob_name="index_lock",
        credential=AzureSyncCredential(),
    )),
)
