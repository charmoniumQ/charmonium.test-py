import abc
import pathlib
from ...types import Condition
from ..measure_command_execution import CompletedContainer


class WorkflowExecutor(abc.ABC):
    @abc.abstractmethod
    def do_commands(self,
            code_dir: pathlib.Path,
            out_dir: pathlib.Path,
            log_dir: pathlib.Path,
            condition: Condition,
    ) -> tuple[CompletedContainer, ...]:
        ...
