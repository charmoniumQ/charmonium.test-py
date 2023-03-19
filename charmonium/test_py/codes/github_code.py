from __future__ import annotations
import dataclasses
from pathlib import Path
import re
import subprocess
import warnings
from typing import Iterable, Optional, Mapping

import github

from charmonium.test_py.types import Code
from .git_code import GitCode
from charmonium.test_py.api import github_client


github_pattern = re.compile(
    "https://github.com/(?P<user>[a-zA-Z0-9-.]+)/(?P<repo>[a-zA-Z0-9-.]+)"
)


def from_url(url: str) -> github.Repository.Repository:
    if url.endswith(".git"):
        url = url[:-4]
    parsed_url = github_pattern.match(url)
    if not parsed_url:
        raise ValueError(f"{url!r} is does not match {github_pattern!r}.")
    return github_client().get_user(parsed_url.group("user")).get_repo(parsed_url.group("repo"))


@dataclasses.dataclass(frozen=True)
class GitHubCode(Code):
    repo: github.Repository.Repository
    commit: github.Commit.Commit
    tag: Optional[github.Tag.Tag] = None

    @staticmethod
    def from_repo(repo: github.Repository.Repository, versions_from: str) -> Iterable[GitHubCode]:
        if versions_from == "commits":
            for commit in repo.get_commits():
                yield GitHubCode(repo, commit)
        elif versions_from == "tags":
            for tag in repo.get_tags():
                yield GitHubCode(repo, tag.commit, tag)
        elif versions_from == "latest":
            yield GitHubCode(repo, next(iter(repo.get_commits())))
        elif versions_from.startswith("releases"):
            skip_drafts = "skip_drafts" in versions_from
            skip_prereleases = "skip_prereleases" in versions_from
            tags = {tag.name: tag for tag in repo.get_tags()}
            for release in repo.get_releases():
                if (not skip_drafts or not release.draft) and (not skip_prereleases or not release.prerelease):
                    tag = tags[release.tag_name]
                    yield GitHubCode(repo, tag.commit, tag)
        else:
            raise NotImplementedError(f"get_versions not implemented for {versions_from!r}")

    @staticmethod
    def create(user: str, repo: str, commit: str, tag: Optional[str] = None) -> GitHubCode:
        grepo = github_client().get_repo(user + "/" + repo)
        gtag: Optional[github.Tag.Tag]
        if tag:
            gtag = next(gtag for gtag in grepo.get_tags() if gtag.name == tag)
        else:
            gtag = None
        return GitHubCode(
            repo=grepo,
            commit=grepo.get_commit(commit),
            tag=gtag,
        )

    def __getstate__(self) -> Mapping[str, Optional[str]]:
        return {
            "full_name": self.repo.full_name,
            "commit": self.commit.sha,
            "tag": self.tag.name if self.tag is not None else None
        }

    def __setstate__(self, state: Mapping[str, Optional[str]]) -> None:
        object.__setattr__(self, "repo", github_client().get_repo(state["full_name"]))
        object.__setattr__(self, "commit", self.repo.get_commit(state["commit"]))
        if state["tag"]:
            gtag = next(gtag for gtag in self.repo.get_tags() if gtag.name == state["tag"])
        else:
            gtag = None
        object.__setattr__(self, "tag", gtag)

    @property
    def html_url(self) -> str:
        if self.tag is not None:
            return "{self.repo.html_url}/tree/{tag.name}"
        else:
            return self.commit.html_url

    def checkout(self, path: Path) -> None:
        GitCode(self.repo.url, self.commit.sha, self.tag.name if self.tag is not None else None).checkout(path)
