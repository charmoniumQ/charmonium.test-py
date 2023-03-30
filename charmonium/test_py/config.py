# import logging, os, pathlib
# for logger_name in ["charmonium.cache.perf", "charmonium.cache.ops", "charmonium.freeze"]:
#     logger = logging.getLogger(logger_name)
#     logger.setLevel(logging.DEBUG)
#     fname = pathlib.Path(logger.name.replace(".", "_") + ".log")
#     if fname.exists() and len(fname.read_text()) > 1024 * 256:
#         fname.unlink()
#     fh = logging.FileHandler(fname)
#     fh.setLevel(logging.DEBUG)
#     fh.setFormatter(logging.Formatter("%(message)s"))
#     logger.addHandler(fh)
#     logger.debug("Program %d", os.getpid())

from charmonium.cache import freeze_config
from charmonium.freeze import global_config
for config in [freeze_config, global_config]:
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
    freeze_config.ignore_objects_by_class.update({
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
