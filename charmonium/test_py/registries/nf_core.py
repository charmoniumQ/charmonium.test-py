import requests
import re

from .github_user import GitHubUser


class NfCoreRegistry(GitHubUser):
    @staticmethod
    def create() -> NfCoreRegistry:
        ignored_repos_ini = requests.get("https://raw.githubusercontent.com/nf-core/nf-co.re/master/ignored_repos.ini").text
        ignored_repos_ini = ignored_repos_ini[:ignored_repos_ini.find("[ignore_topics]")]
        return NfCoreRegistry(
            user="nf-core",
            versions_from="releases skip_prereleases skip_drafts",
            ignored_repos={
                match.group(1)
                for match in re.finditer(r"repos\[\] = \"(.*)\"", ignored_repos_ini)
            },
        )
