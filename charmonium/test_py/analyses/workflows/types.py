import dataclasses
import datetime 
import pathlib
from typing import Mapping, Optional

from ...types import Analysis, Result
from ...util import create_temp_dir
from ..measure_comand_execution import measure_command_execution, ComputeResources
from ...file_bundle import FileBundle


class Engine:
    def get_executable(
            self,
            workflow: pathlib.Path,
            log_dir: pathlib.Path,
            out_dir: pathlib.Path,
            n_cores: int
    ) -> tuple[tuple[str, ...], Mapping[str, str]]: ...


class WorkflowExecution(Result):
    machine: Optional[Machine]
    datetime: datetime.datetime
    outputs: FileBundle
    logs: FileBundle
    resources: ComputeResources
    status_code: int

    @property
    def successful(self) -> bool:
        return self.status_code == 0


@dataclasses.dataclass
class RunWorkflow(Analysis):
    storage: upath.UPath

    def analyze(self, code: pathlib.Path) -> Result:
        with create_temp_dir() as path:
            code_dir = path / "code"
            log_dir = path / "log"
            out_dir = path / "out"
            for dir in [code_dir, log_dir, out_dir]:
                dir.mkdir()
            now = datetime.datetime.now()
            engine = Engine() # TODO
            cmd, env = engine.get_executable(code, log_dir, out_dir,
                                             n_cores) # TODO
            proc = measure_command_execution(cmd, emv, timeout)
            (log_dir / "stdout.txt").write_bytes(proc.stdout)
            (log_dir / "stderr.txt").write_bytes(proc.stderr)
            (log_dir / "command.sh").write_text("\n".join([
                "git clone", # TODO
                env_command(cmd, env),
            ]))
        return WorkflowExecution(
            machine=Machine.current(),
            datetime=now,
            outputs=FileBundle.create_in_storage(out_dir, storage / "stdout.tar.xz"),
            logs=FileBundle.create_in_storage(log_dir, storage / "stdout.tar.xz"),
            resources=proc.resources,
            status_code=proc.returncode,
        )
