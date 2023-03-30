import dataclasses
import datetime
import os
import pathlib
import shlex
import subprocess
import warnings
import textwrap
from typing import Iterable, Mapping

import psutil


from ..util import create_temp_dir
from ..api import docker_client


@dataclasses.dataclass(frozen=True)
class ComputeResource:
    user_cpu_time: datetime.timedelta
    system_cpu_time: datetime.timedelta
    wall_time: datetime.timedelta
    max_resident_set_size: int
    max_virtual_memory_size: int | None = None
    io_bytes_read: int | None = None
    io_bytes_written: int | None = None
    scheduler_context_switches: int | None = None


@dataclasses.dataclass(frozen=True)
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
                for key, val in self.env.items()
            ),
            *self.command
        )

    def raise_for_status(self) -> None:
        if self.status != 0:
            raise CalledProcessError(self)


@dataclasses.dataclass(frozen=True)
class CalledProcessError(Exception):
    process: CompletedProcess
    def __str__(self) -> str:
        return f"""
Command: {shlex.join(self.process.command)}
Status: {self.process.status}
Start: {self.process.start.isoformat()}
Full command: {shlex.join(self.process.env_command)}
Stdout:
{textwrap.indent(self.process.stdout, "  ")}
Stderr:
{textwrap.indent(self.process.stderr, "  ")}
"""


def measure_command_execution(
        command: tuple[str, ...],
        env_override: Mapping[str, str] | None = None,
        clear_env: bool = False,
        cwd: pathlib.Path = pathlib.Path(),
) -> CompletedProcess:
    env = {} if clear_env else dict(os.environ)
    if env_override is not None:
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
    status = process.wait()
    with process.oneshot():
        wall_time = datetime.datetime.now() - start
        cpu_times = process.cpu_times()
        io_counters = process.io_counters()  # type: ignore
        memory_info = process.memory_info()
        resource = ComputeResource(
            user_cpu_time=datetime.timedelta(seconds=cpu_times.user),
            system_cpu_time=datetime.timedelta(seconds=cpu_times.system),
            max_resident_set_size=memory_info.rss,
            max_virtual_memory_size=memory_info.vms,
            wall_time=wall_time,
            io_bytes_read=io_counters.read_bytes,
            io_bytes_written=io_counters.write_bytes,
            scheduler_context_switches=process.ctx_switches()
        )
    return CompletedProcess(
        command=command,
        env=env,
        cwd=cwd,
        resource=resource,
        status=status,
        start=start,
        stdout_b=process.stdout,
        stderr_b=process.stderr,
    )


@dataclasses.dataclass(frozen=True)
class CompletedContainer:
    image: str
    command: tuple[str, ...]
    docker_command: str
    resource: ComputeResource
    status: int
    start: datetime.datetime
    stdout_b: bytes
    stderr_b: bytes


def measure_docker_execution(
        image: str,
        command: tuple[str, ...],
        *,
        wall_time_limit: datetime.timedelta,
        mem_limit: int,
        cpus: float,
        privileged: bool = False,
        readonly_mounts: tuple[pathlib.Path, ...] = (),
        readwrite_mounts: tuple[pathlib.Path, ...] = (),
        kill_after: datetime.timedelta = datetime.timedelta(seconds=120),
) -> CompletedContainer:
    with create_temp_dir() as temp_dir:
        resource_file = temp_dir / "resources"
        stdout_file = temp_dir / "stdout"
        stderr_file = temp_dir / "stderr"
        real_command = (
            "-i",
            "-c",
            # shlex.join would mess up the \ and > symbols.
            " ".join([
                # We use the \ to make sure we don't invoke the bash time internal
                r"\time",
                f"--output={shlex.quote(str(resource_file))}",
                "--format='%M %S %U %e %x'",
                "timeout",
                f"--kill-after={kill_after.total_seconds():.0f}",
                f"{wall_time_limit.total_seconds():.0f}",
                *map(shlex.quote, command),
                f">{shlex.quote(str(stdout_file))}",
                f"2>{shlex.quote(str(stderr_file))}",
            ]),
        )
        volumes = {
            str(temp_dir): {"bind": str(temp_dir), "mode": "rw"},
            **{
                str(mount): {"bind": str(mount), "mode": "ro"}
                for mount in readonly_mounts
            },
            **{
                str(mount): {"bind": str(mount), "mode": "rw"}
                for mount in readwrite_mounts
            },
        }
        container = docker_client().containers.run(
            image,
            real_command,
            privileged=privileged,
            mem_limit=mem_limit,
            auto_remove=False,
            detach=True,
            nano_cpus=int(cpus * 1e9),
            volumes=volumes,
            entrypoint="/bin/bash",
        )
        start = datetime.datetime.now()
        try:
            container.wait()
        finally:
            container.remove()
        time_output = (
            resource_file.read_text().strip().split("\n")
            if resource_file.exists()
            else ""
        )
        stdout = stdout_file.read_bytes()
        stderr = stderr_file.read_bytes()
        try:
            mem_kb, system_sec, user_sec, wall_time, exit_status = time_output[-1].split(" ")
        except (ValueError, IndexError):
            mem_kb = "0"
            system_sec = "0.0"
            user_sec = "0.0"
            wall_time = "0.0"
            exit_status = "0"
            warnings.warn(
                f"Could not parse time output: {time_output!r}; setting those fields to 0"
            )
    return CompletedContainer(
        docker_command=" && ".join([
            shlex.join(["mkdir", "-p", f"{temp_dir}"]),
            shlex.join([
                "docker",
                "run",
                "--entrypoint=/bin/bash",
                f"--privileged={privileged!s}",
                f"--memory={mem_limit}b",
                f"--cpus={cpus:0.2f}",
                *[
                    f"--volume={host_dir}:{options['bind']}:{options['mode']}"
                    for host_dir, options in volumes.items()
                ],
                image,
                *real_command,
            ]),
        ]),
        command=command,
        image=image,
        status=int(exit_status),
        start=start,
        stdout_b=stdout,
        stderr_b=stderr,
        resource=ComputeResource(
            user_cpu_time=datetime.timedelta(seconds=float(user_sec)),
            system_cpu_time=datetime.timedelta(seconds=float(system_sec)),
            wall_time=datetime.timedelta(seconds=float(wall_time)),
            max_resident_set_size=int(mem_kb) * 1024,
        ),
    )
