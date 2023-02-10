import csv
import dataclasses
from pathlib import Path
from typing import Iterable
import warnings
import re

from charmonium.test_py.types import ProjectRegistry, Project
from charmonium.test_py.projects import GitProject


@dataclasses.dataclass(frozen=True)
class FlaPyRegistry(ProjectRegistry):
    csv_path: Path

    def get_versions(self) -> Iterable[Project]:
        with self.csv_path.open() as file:
            reader = csv.reader(file)
            for line in reader:
                if line[3] or line[4] or line[5]:
                    warnings.warn("Columns 3, 4, 5 are not implemented.")
                name = line[0]
                repo_url = line[1]
                rev = line[2]
                yield GitProject(
                    repo_url,
                    versions_from="fixed",
                    fixed_versions=(rev,),
                )
