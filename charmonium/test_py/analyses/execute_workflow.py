import abc
import dataclasses
import pathlib

from .types import Analysis, Code, Condition, Result


class ExecuteWorkflow(Analysis):
    def analyze(
        self,
        code: Code,
        condition: Condition,
    ) -> Result:
        pass


@dataclasses.dataclass
class WorkflowExecution:
    pass


class WorkflowExecutor(abc.ABC):
    def get_container(self,
            code_dir: pathlib.Path,
            out_dir: pathlib.Path,
            log_dir: pathlib.Path,
            n_cores: int,
            conditoins: Conditions,
    ) -> tuple[str, tuple[str, ...]]:
        pass


executors: dict[str, WorkflowExecutor] = {}
