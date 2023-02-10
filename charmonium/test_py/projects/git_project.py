import dataclasses
from pathlib import Path
import subprocess
import warnings
import shutil
from typing import Iterable, Optional

import git

from charmonium.test_py.types import Project, Version


@dataclasses.dataclass(frozen=True)
class GitProject(Project):
    repo_url: str
    versions_from: str
    fixed_versions: Optional[tuple[str]] = None

    def get_versions(self, path: Path) -> Iterable[Version]:
        repo = git.repo.Repo.clone_from(self.repo_url, path)
        if self.versions_from == "commits":
            for commit in repo.iter_commits():
                yield GitVersion(self.repo_url, commit.hexsha)
        elif self.versions_from == "tags":
            for tag in repo.tags:
                yield GitVersion(self.repo_url, tag.commit.hexsha)
        elif self.versions_from == "fixed":
            assert self.fixed_versions is not None
            for rev in self.fixed_versions:
                yield GitVersion(self.repo_url, rev)
        else:
            raise NotImplementedError(f"get_versions not implemented for {self.versions_from!r}")


@dataclasses.dataclass(frozen=True)
class GitVersion(Version):
    repo_url: str
    rev: str

    def checkout(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)
        repo = git.repo.Repo.clone_from(self.repo_url, path)
        repo.head.reset(self.rev, index=True, working_tree=True)
        repo.submodule_update(recursive=True)
