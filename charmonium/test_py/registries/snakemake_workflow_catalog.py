import dataclasses
from typing import Iterable
import json
import requests

from ..types import Registry
from ..codes import GitHubCode, WorkflowCode
from ..config import github_client


@dataclasses.dataclass(frozen=True)
class SnakemakeWorkflowCatalog(Registry):
    def get_codes(self) -> Iterable[WorkflowCode]:
        """
        Takes <1s to get all 1781 workflows in the Snakemake-workflow-catalog

        Source: https://github.com/snakemake/snakemake-workflow-catalog/blob/main/scripts/generate-catalog.py
        See also: https://snakemake.github.io/snakemake-workflow-catalog/
        """
        url = "https://raw.githubusercontent.com/snakemake/snakemake-workflow-catalog/main/data.js"
        repo_infos = json.loads(requests.get(url, timeout=10).text.partition("\n")[2])
        for repo_info in repo_infos:
            if repo_info["standardized"]:
                user, repo_name = repo_info["full_name"].split("/")
                repo = github_client().get_user(user).get_repo(repo_name)
                for code in GitHubCode.from_repo(
                    repo,
                    versions_from="tags",
                ):
                    yield WorkflowCode(code, "snakemake")
