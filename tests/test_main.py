import io
import os
import pathlib
import datetime

from charmonium.test_py.analyses.measure_command_execution import measure_container_execution


def test_mce() -> None:
    import docker
    client = docker.from_env()
    image = client.images.build(
        fileobj=io.BytesIO(b"\n".join([
            b"FROM python:3-slim",
            b"RUN apt-get update && apt-get install -y time coreutils"
        ])),
        tag="python-test",
    )
    script = """
len(b"a" * {mem})
import datetime
start = datetime.datetime.now()
while datetime.datetime.now() < start + datetime.timedelta(seconds={time}):
    pass
import sys
sys.stdout.write("stdout")
sys.stderr.write("stderr")
sys.exit(111)
"""
    mem = 1024 * 1024 * 8
    time = datetime.timedelta(seconds=2)
    start = datetime.datetime.now()
    process = measure_container_execution(
        "python-test",
        ("python", "-c", script.format(mem=mem, time=time.total_seconds())),
        wall_time_limit=datetime.timedelta(seconds=10),
        mem_limit=1024 * 1024 * 1024,
        cpus=1.0,
    )
    assert process.docker_command
    assert process.status == 111
    assert start < process.start < start + time
    assert process.stdout_b == b"stdout"
    assert process.stderr_b == b"stderr"
    assert time < process.resource.wall_time < 1.5 * time
    assert time < process.resource.user_cpu_time < 1.5 * time
    # base_mem is the memory taken by the default Python interpreter under no load
    # It is empirically derived with the following command:
    #     /usr/bin/time --format "1024 * %M" python -c 'pass'
    base_mem = 1024 * 9200
    assert mem < process.resource.max_resident_set_size < mem * 1.5 + base_mem
