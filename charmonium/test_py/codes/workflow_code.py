import dataclasses
import pathlib

from ..types import Code

@dataclasses.dataclass(frozen=True)
class WorkflowCode(Code):
    code: Code
    executor: str

    def checkout(self, path: pathlib.Path) -> None:
        self.code.checkout(path)
