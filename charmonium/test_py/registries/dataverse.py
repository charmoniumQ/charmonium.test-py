from typing import Iterable

from ..codes import WorkflowCode, DataverseDataset
from ..types import Registry

# TODO: A cleaner implementation would use [pyDataverse], an optional [API token], use parallelism, and search for q=*&type=dataset.
# [pyDataverse]: https://github.com/gdcc/pyDataverse
# [API token]: https://guides.dataverse.org/en/4.18.1/api/auth.html
class Dataverse(Registry):
    def get_codes(self) -> Iterable[WorkflowCode]:
        raise NotImplementedError
