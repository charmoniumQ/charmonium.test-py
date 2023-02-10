import dataclasses
from typing import Iterable
import json
import requests

from charmonium.test_py.types import ProjectRegistry, Project
from charmonium.test_py.projects import GitHubProject


@dataclasses.dataclass(frozen=True)
class SnakemakeWorkflowCatalog(ProjectRegistry):
    def get_project(self) -> Iterable[Project]:
        """
        Takes <1s to get all 1781 workflows in the Snakemake-workflow-catalog

        Source: https://github.com/snakemake/snakemake-workflow-catalog/blob/main/scripts/generate-catalog.py
        See also: https://snakemake.github.io/snakemake-workflow-catalog/
        """
        url = "https://raw.githubusercontent.com/snakemake/snakemake-workflow-catalog/main/data.js"
        repo_infos = json.loads(requests.get(url, timeout=10).text.partition("\n")[2])
        for repo_info in repo_infos:
            if repo_info["standardized"]:
                user, repo = repo_info["full_name"].split("/")
                yield GitHubProject.from_parts(
                    user=user,
                    repo=repo,
                    versions_from="tags",
                )
