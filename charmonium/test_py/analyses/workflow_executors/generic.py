import abc
import pathlib
from ...types import Condition


class WorkflowExecutor(abc.ABC):
    @abc.abstractmethod
    def get_container(self,
            code_dir: pathlib.Path,
            out_dir: pathlib.Path,
            log_dir: pathlib.Path,
            cpus: int,
            mem_limit: int,
            condition: Condition,
    ) -> tuple[str, tuple[str, ...]]:
        ...
