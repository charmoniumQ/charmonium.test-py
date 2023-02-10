import dataclasses
import datetime
import pathlib

import git

from charmonium.test_py.types import Analysis, Version, Condition, Result


@dataclasses.dataclass
class GitCommitInfo(Result):
    hexsha: str
    authored_datetime: datetime.datetime
    committed_datetime: datetime.datetime
    message: str
    n_parents: int
    author: str
    co_authors: list[str]
    committer: str

class AnalyzeGitCommit(Analysis):
    def analyze(
            self,
            path: pathlib.Path,
    ) -> GitCommitInfo:
        repo = git.repo.Repo(path)
        commit = repo.head.commit
        return GitCommitInfo(
            commit.hexsha,
            commit.authored_datetime,
            commit.committed_datetime,
            commit.message,
            len(commit.parents),
            commit.author.email,
            [actor.email for actor in commit.co_authors],
            commit.committer.email,
        )
