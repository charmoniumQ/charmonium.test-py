import requests
import dataclasses
from typing import Iterable

from ..codes import WorkflowCode, DataverseDataset
from ..types import Registry

@dataclasses.dataclass
class DataverseTrisovicFixed(Registry):
    url = "https://raw.githubusercontent.com/atrisovic/dataverse-r-study/master/get-dois/dataset_dois.txt"
    def get_codes(self) -> Iterable[WorkflowCode]:
        for persistent_id in requests.get(self.url).text.strip().split("\n"):
            yield WorkflowCode(DataverseDataset(persistent_id), "R")
