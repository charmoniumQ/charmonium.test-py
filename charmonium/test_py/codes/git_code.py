from __future__ import annotations
import dataclasses
from pathlib import Path
import subprocess
import warnings
import shutil
from typing import Iterable, Optional

import git

from charmonium.test_py.types import Code
from charmonium.test_py.util import create_temp_dir


@dataclasses.dataclass(frozen=True)
class GitCode(Code):
    repo_url: str
    rev: str
    tag_name: Optional[str] = None

    @staticmethod
    def all_versions(repo_url: str, versions_from: str) -> Iterable[GitCode]:
        """Gets all versions (commits from the default branch or tags)."""
        with create_temp_dir() as temp_dir:
            repo = git.repo.Repo.clone_from(repo_url, temp_dir)
            if versions_from == "commits":
                for commit in repo.iter_commits():
                    yield GitCode(repo_url, commit.hexsha)
            elif versions_from == "tags":
                for tag in repo.tags:
                    yield GitCode(repo_url, tag.commit.hexsha, tag.name)
            elif versions_from == "latest":
                yield GitCode(repo_url, next(repo.iter_commits()).hexsha, repo.head.name)
            else:
                raise NotImplementedError(f"get_versions not implemented for {versions_from!r}")

    def checkout(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)
        repo = git.repo.Repo.clone_from(self.repo_url, path)
        repo.head.reset(self.rev, index=True, working_tree=True)
        repo.submodule_update(recursive=True)
