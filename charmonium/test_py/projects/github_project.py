import dataclasses
from pathlib import Path
import re
import subprocess
import warnings
from typing import Iterable, Optional

import github

from charmonium.test_py.types import Project, Version
from .git_project import GitVersion
from charmonium.test_py.api import github_client


github_pattern = re.compile(
    "https://github.com/(?P<user>[a-zA-Z0-9-.]+)/(?P<repo>[a-zA-Z0-9-.]+)"
)


@dataclasses.dataclass(frozen=True)
class GitHubProject(Project):
    @staticmethod
    def from_parts(user: str, repo: str, versions_from: str = "tags") -> GitHubProject:
        return GitHubProject(
            repo=github_client().get_user(user).get_repo(repo),
            versions_from=versions_from,
        )

    repo: github.Repository.Repository

    versions_from: str = "tags"
  
    @staticmethod
    def from_url(url: str, versions_from: str ="tags") -> GitHubProject:
        if url.endswith(".git"):
            url = url[:-4]
        parsed_url = github_pattern.match(url)
        if not parsed_url:
            raise ValueError(f"{url!r} is does not match {github_pattern!r}.")
        return GitHubProject.from_parts(
            parsed_url.group("user"),
            parsed_url.group("repo"),
            versions_from,
        )

    @property
    def repo_url(self) -> str:
        return self.repo.url

    @property
    def html_url(self) -> str:
        return self.repo.html_url

    def get_versions(self, _path: Path) -> Iterable[Version]:
        if self.versions_from == "commits":
            for commit in self.repo.get_commits():
                yield GitHubVersion(self.repo, commit)
        elif self.versions_from == "tags":
            for tag in self.repo.get_tags():
                yield GitHubVersion(self.repo, tag.commit, tag)
        elif self.versions_from.startswith("releases"):
            skip_drafts = "skip_drafts" in self.versions_from
            skip_prereleases = "skip_prereleases" in self.versions_from
            tags = {tag.name: tag for tag in self.repo.get_tags()}
            for release in self.repo.get_releases():
                if (not skip_drafts or not release.draft) and (not skip_prereleases or not release.prerelease):
                    tag = tags[release.tag_name]
                    yield GitHubVersion(self.repo, tag.commit, tag)
        else:
            raise NotImplementedError(f"get_versions not implemented for {self.versions_from!r}")


@dataclasses.dataclass(frozen=True)
class GitHubVersion(Version):
    repo: github.Repository.Repository
    commit: github.Commit.Commit
    tag: Optional[github.Tag.Tag] = None

    @staticmethod
    def create(user: str, repo: str, commit: str, tag: Optional[str] = None) -> GitHubVersion:
        grepo = github_client().get_user(user).get_repo(repo)
        gtag: Optional[github.Tag.Tag]
        if tag:
            gtag = next(gtag for gtag in grepo.get_tags() if gtag.name == tag)
        else:
            gtag = None
        return GitHubVersion(
            repo=grepo,
            commit=grepo.get_commit(commit),
            tag=gtag,
        )

    @property
    def html_url(self) -> str:
        if self.tag is not None:
            return "{self.repo.html_url}/tree/{tag.name}"
        else:
            return self.commit.html_url

    def checkout(self, path: Path) -> None:
        GitVersion(self.repo.url, self.commit.sha).checkout(path)
