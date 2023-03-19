import dataclasses
import datetime
import pathlib
from typing import Optional

import git

from charmonium.test_py.types import Analysis, Code, Condition, Result


@dataclasses.dataclass
class GitInfoResult(Result):
    hexsha: str
    authored_datetime: datetime.datetime
    committed_datetime: datetime.datetime
    message: Optional[str]
    n_parents: int
    author: Optional[str]
    committer: Optional[str]
    co_authors: list[str]

class GitInfo(Analysis):
    def analyze(
            self,
            code: Code,
            condition: Condition,
            code_path: pathlib.Path,
    ) -> GitInfoResult:
        repo = git.repo.Repo(code_path)
        commit = repo.head.commit
        message = commit.message
        author_email = commit.author.email
        committer_email = commit.committer.email
        return GitInfoResult(
            commit.hexsha,
            commit.authored_datetime,
            commit.committed_datetime,
            str(message) if message is not None else None,
            len(commit.parents),
            str(author_email) if author_email is not None else None,
            str(committer_email) if committer_email is not None else None,
            [str(actor.email) for actor in commit.co_authors if actor.email is not None],
        )
