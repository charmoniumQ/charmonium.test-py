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


class ExecuteWorkflow(Analysis):
    def analyze(
        self,
        code: Code,
        condition: Condition,
        code_path: pathlib.Path
    ) -> Result:
        code = expect_type(WorkflowCode, code)
        with create_temp_dir() as tmp_path:
            log_dir = tmp_path / "log"
            out_dir = tmp_path / "out"
            for dir in [log_dir, out_dir]:
                dir.mkdir()
            executor = executors[code.executor]
            # TODO: gret these in a more systematic way
            mem_limit = 1024**3
            cpus = 1
            wall_time_limit = datetime.timedelta(hours=1)
            image, command = executor.get_container(code_path, out_dir, log_dir, cpus, mem_limit, condition)
            proc = measure_docker_execution(
                image,
                command,
                mem_limit=mem_limit,
                cpus=cpus,
                readwrite_binds=(tmp_path, code_path,),
                wall_time_limit=wall_time_limit,
            )
            (log_dir / "stdout.txt").write_bytes(proc.stdout_b)
            (log_dir / "stderr.txt").write_bytes(proc.stderr_b)
            (log_dir / "command.sh").write_text(proc.docker_command)
            for src in walk_files(code_path):
                if src.is_file() and mtime(src) >= proc.start:
                    dst = out_dir / src.relative_to(code_path)
                    dst.parent.mkdir(exist_ok=True, parents=True)
                    shutil.move(src, dst)
            outputs = FileBundle.from_path(out_dir)
            logs = FileBundle.from_path(log_dir)
            chown(tmp_path)
            chown(code_path)
        return WorkflowExecution(
            limits={"mem": mem_limit, "cpus": cpus},
            machine=Machine.current_machine(),
            image=image,
            command=command,
            outputs=outputs,
            logs=logs,
            condition=condition,
            proc=proc,
        )


@dataclasses.dataclass(frozen=True)
class WorkflowExecution(Result):
    limits: Mapping[str, object]
    machine: Machine
    image: str
    command: tuple[str, ...]
    outputs: FileBundle
    logs: FileBundle
    condition: Condition
    proc: CompletedContainer
