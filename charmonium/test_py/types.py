from pathlib import Path
from typing import Iterable, Mapping, Optional
import dataclasses


class Condition:
    pass


class Version:
    def checkout(self, path: Path) -> None: ...


class Project:
    def get_versions(self, path: Path) -> Iterable[Version]: ...


class ProjectRegistry:
    def get_projects(self) -> Iterable[Project]: ...


class Analysis:
    def analyze(self, code: Path) -> Result: ...


class Result:
    pass


class Environment:
    def install(self, code: Path, new_env: Path, past_env: Optional[Path]) -> None: ...
    env: Mapping[str, str]
