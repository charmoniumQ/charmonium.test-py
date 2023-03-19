import requests
import re
from typing import Iterable

from charmonium.test_py.codes import WorkflowCode
from charmonium.test_py.types import Registry

from .github_user import GitHubUser


class NfCoreRegistry(Registry):
    def get_codes(self) -> Iterable[WorkflowCode]:
        ignored_repos_ini = requests.get("https://raw.githubusercontent.com/nf-core/nf-co.re/master/ignored_repos.ini").text
        ignored_repos_ini = ignored_repos_ini[:ignored_repos_ini.find("[ignore_topics]")]
        registry = GitHubUser(
            user="nf-core",
            versions_from="releases skip_prereleases skip_drafts",
            ignored_repos={
                match.group(1)
                for match in re.finditer(r"repos\[\] = \"(.*)\"", ignored_repos_ini)
            },
        )
        for code in registry.get_codes():
            yield WorkflowCode(code, "nextflow")
