import dataclasses
from typing import Iterable
import json
import requests
import re

from charmonium.test_py.types import ProjectRegistry, Project
from charmonium.test_py.projects import GitHubProject
from charmonium.test_py.api import github_client


@dataclasses.dataclass(frozen=True)
class GitHubUser(ProjectRegistry):
    user: str
    versions_from: str
    ignored_repos: set[str]

    def get_project(self) -> Iterable[Project]:
        repos = github_client().get_user(self.user).get_repos()
        for repo in repos:
            if repo.name not in self.ignored_repos:
                yield GitHubProject.from_parts(
                    user=repo.owner.login,
                    repo=repo.name,
                    versions_from=self.versions_from,
                )
