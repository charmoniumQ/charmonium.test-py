from __future__ import annotations
import dataclasses
from pathlib import Path
import re
import subprocess
import warnings
import functools
from typing import Iterable, Optional, Mapping, Any

import github

from ..types import Code
from .git_code import GitCode
from ..api import github_client


@dataclasses.dataclass(frozen=True)
class GitHubCode(Code):
    _user: str
    _repo: str
    _commit: str
    _tag: Optional[str]

    @functools.cached_property
    def repo(self) -> github.Repository.Repository:
        return github_client().get_repo(self._user + "/" + self._repo)

    @functools.cached_property
    def commit(self) -> github.Commit.Commit:
        return self.repo.get_commit(self._commit)

    @functools.cached_property
    def tag(self) -> Optional[github.Tag.Tag]:
        return next(gtag for gtag in self.repo.get_tags() if gtag.name == self._tag)

    def __getstate__(self) -> Mapping[str, Any]:
        # Note that functools.cached_property writes a github.* object to self, if accessed.
        # This object contains an RLock, which is unpicklable.
        # Therefore, I exclude this from pickling.
        return {
            "_user": self._user,
            "_repo": self._repo,
            "_commit": self._commit,
            "_tag": self._tag,
        }

    def __setstate__(self, dct: Mapping[str, Any]) -> None:
        for key, val in dct.items():
            object.__setattr__(self, key, val)

    @staticmethod
    def from_repo(repo: github.Repository.Repository, versions_from: str) -> Iterable[GitHubCode]:
        if versions_from == "commits":
            for commit in repo.get_commits():
                yield GitHubCode.create(repo, commit, None)
        elif versions_from == "tags":
            for tag in repo.get_tags():
                yield GitHubCode.create(repo, tag.commit, tag)
        elif versions_from == "latest":
            commit = next(iter(repo.get_commits()))
            yield GitHubCode.create(repo, commit, None)
        elif versions_from.startswith("releases"):
            skip_drafts = "skip_drafts" in versions_from
            skip_prereleases = "skip_prereleases" in versions_from
            tags = {tag.name: tag for tag in repo.get_tags()}
            for release in repo.get_releases():
                if (not skip_drafts or not release.draft) and (not skip_prereleases or not release.prerelease):
                    tag = tags[release.tag_name]
                    yield GitHubCode.create(repo, tag.commit, tag)
        else:
            raise NotImplementedError(f"get_versions not implemented for {versions_from!r}")

    @staticmethod
    def create(
            repo: github.Repository.Repository,
            commit: github.Commit.Commit,
            tag: Optional[github.Tag.Tag],
    ) -> GitHubCode:
        ghc = GitHubCode(repo.owner.login, repo.name, commit.sha, tag.name if tag is not None else None)
        object.__setattr__(ghc, "repo", repo)
        object.__setattr__(ghc, "commit", commit)
        object.__setattr__(ghc, "tag", tag)
        return ghc

    @property
    def html_url(self) -> str:
        if self.tag is not None:
            return "{self.repo.html_url}/tree/{tag.name}"
        else:
            return self.commit.html_url

    def checkout(self, path: Path) -> None:
        GitCode(self.repo.url, self.commit.sha, self.tag.name if self.tag is not None else None).checkout(path)
