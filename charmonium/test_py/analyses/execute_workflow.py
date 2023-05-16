import abc
import dataclasses
import datetime
import pathlib
import shlex
import shutil
from typing import Mapping

from ..types import Analysis, Code, Condition, Result
from ..util import create_temp_dir, expect_type, mtime, walk_files, chown
from ..codes import WorkflowCode
from .file_bundle import FileBundle
from .measure_command_execution import CompletedContainer, measure_docker_execution
from .machine import Machine
from .workflow_executors import executors, WorkflowExecutor
from ..conditions import WorkflowCondition


class ExecuteWorkflow(Analysis):
    def analyze(
        self,
        code: Code,
        condition: Condition,
        code_path: pathlib.Path
    ) -> Result:
        code = expect_type(WorkflowCode, code)
        condition = expect_type(WorkflowCondition, condition)
        with create_temp_dir() as tmp_path:
            log_dir = tmp_path / "log"
            out_dir = tmp_path / "out"
            for dir in [log_dir, out_dir]:
                dir.mkdir()
            executor = executors[code.executor]
            procs = executor.do_commands(code_path, out_dir, log_dir, condition)
            for src in walk_files(code_path):
                if procs and src.is_file() and mtime(src) >= procs[0].start:
                    dst = out_dir / src.relative_to(code_path)
                    dst.parent.mkdir(exist_ok=True, parents=True)
                    shutil.move(src, dst)
            outputs = FileBundle.from_path(out_dir)
            logs = FileBundle.from_path(log_dir)
            chown(tmp_path)
            chown(code_path)
        return WorkflowExecution(
            machine=Machine.current_machine(),
            outputs=outputs,
            logs=logs,
            condition=condition,
            procs=procs,
        )


@dataclasses.dataclass(frozen=True)
class WorkflowExecution(Result):
    machine: Machine
    outputs: FileBundle
    logs: FileBundle
    condition: Condition
    procs: tuple[CompletedContainer, ...]
