import logging, os
logger = logging.getLogger("charmonium.freeze")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("freeze.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(fh)
logger.debug("Program %d", os.getpid())

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
    })
    config.ignore_functions.update({
        ("requests.api", "get"),
        ("git.cmd", "is_cygwin"),
        ("git.repo.base", "__init__"),
        ("git.repo.base", "_clone"),
        ("json", "loads"),
    })
