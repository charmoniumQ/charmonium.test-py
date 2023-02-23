import dataclasses
import datetime
import os
import pathlib
import shlex
import subprocess
import textwrap
from typing import Iterable, Mapping

import psutil


@dataclasses.dataclass
class ComputeResource:
    user_cpu_time: datetime.timedelta
    system_cpu_time: datetime.timedelta
    wall_time: datetime.timedelta
    max_resident_set_size: int
    max_virtual_memory_size: int
    io_bytes_read: int
    io_bytes_written: int
    scheduler_context_switches: int


@dataclasses.dataclass
class CompletedProcess:
    command: tuple[str, ...]
    env: Mapping[str, str]
    cwd: pathlib.Path
    resource: ComputeResource
    status: int
    start: datetime.datetime
    stdout_b: bytes
    stderr_b: bytes

    @property
    def stdout(self) -> str:
        return self.stdout_b.decode()

    @property
    def stderr(self) -> str:
        return self.stderr_b.decode()

    @property
    def env_command(self) -> tuple[str, ...]:
        return (
            "env",
            f"--chdir={self.cwd}",
            "-",
            *(
                f"{key}={val}"
                for key, val in self.env_override.items()
            ),
            *self.command
        )

    def raise_for_status(self) -> None:
        if self.status != 0:
            raise CalledProcessError(self)


@dataclasses.dataclass
class CalledProcessError:
    process: CompletedProcess
    def __str__(self) -> str:
        if 
        return f"""
Command: {shlex.join(process.command)}
Status: {process.status}
Start: {process.start.isoformat()}
Full command: {shlex.join(process.env_command)}
Stdout:
{textwrap.indent(process.stdout, "  ")}
Stderr:
{textwrap.indent(process.stderr, "  ")}
"""


def measure_command_execution(
        command: tuple[str, ...],
        env_override: Mapping[str, str],
        clear_env: bool = False,
        cwd: pathlib.Path = pathlib.Path(),
) -> CompletedProcess:
    env = {} if clear_env else os.environ
    env.update(env_override)
    cwd = cwd.resolve()
    start = datetime.datetime.now()
    process = psutil.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=cwd,
    )
    process.wait()
    wall_time = datetime.datetime.now() - start
    with process.oneshot():
        cpu_times = process.cpu_times()
        io_counters = process.io_counters()
        memory_info = process.memory_info()
        resource = ComputeResource(
            user_cpu_time=datetime.timedelta(seconds=cpu_times.user),
            system_cpu_time=datetime.timedelta(seconds=cpu_times.system),
            idle_time=datetime.timedelta(seconds=cpu_times.system),
            max_resident_set_size=memory_info.rss,
            max_virtual_memory_size=memory_info.vss,
            wall_time=wall_time,
            io_bytes_read=io_counters.read_bytes,
            io_bytes_written=io_counters.write_bytes,
            scheduler_context_switches=process.ctx_switches()
        )
    return subprocess.CompletedProcess(
        command=command,
        env=env,
        cwd=cwd,
        resource=resource,
        status=process.status(),
        start=start,
        stdout_b=process.stdout,
        stderr_b=process.stderr,
    )
