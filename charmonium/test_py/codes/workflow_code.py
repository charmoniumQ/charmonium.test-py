import dataclasses
import pathlib

from charmonium.test_py.types import Code

@dataclasses.dataclass(frozen=True)
class WorkflowCode(Code):
    code: Code
    engine: str

    def checkout(self, path: pathlib.Path) -> None:
        self.code.checkout(path)
