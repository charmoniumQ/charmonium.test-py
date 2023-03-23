import dataclasses
from typing import Iterable
import json
import requests
import re

from ..types import Registry, Code
from ..api import github_client
from ..codes import GitHubCode


@dataclasses.dataclass(frozen=True)
class GitHubUser(Registry):
    user: str
    versions_from: str
    ignored_repos: set[str]

    def get_codes(self) -> Iterable[GitHubCode]:
        repos = github_client().get_user(self.user).get_repos()
        for repo in repos:
            if repo.name not in self.ignored_repos:
                yield from GitHubCode.from_repo(
                    repo,
                    self.versions_from,
                )
